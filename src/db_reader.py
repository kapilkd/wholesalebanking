"""
Deterministic data-access layer for the tab-rendering pipeline.

Implements the first stage of the SQL flow described in CLAUDE.md:

    CREATE VIEW per tab  ->  Rules layer  ->  LLM narration

Everything here is plain SQL against the views in DB-Design-Schema/Views/
(plus master-table lookups for code resolution). No LLM is involved at any
point — callers pass the returned rows onward as narration context.

Two entry points matter to the app:

- resolve_lookup_code(code, code_type): validates the code against the
  masters. An APR_CLIENT_CODE resolves to one client (or None if unknown).
  An RM_CODE resolves to the RM plus their actively-mapped clients — the
  data source for the client-picker UX, since every tab view is keyed by
  APR_CLIENT_CODE, not RM_CODE.
- fetch_all_tab_data(client_code): fetches every tab's summary view and all
  six chart views in parallel, returning one dict ready for the rules /
  narration steps.

Row dicts use lower_snake_case keys (matching SummaryState conventions in
src/multi_agent_generator.py) and JSON-safe values: NUMERIC -> float,
DATE/TIMESTAMP -> ISO string.
"""
import datetime
import decimal
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from typing import Any, Dict, List, Optional

from config.db_config import get_db_connection, get_readonly_db_connection

# Upper bound on concurrent view fetches. Must not exceed pool_size in
# config/db_config.py (5) — mysql.connector's pool raises PoolError
# immediately when exhausted instead of queueing.
MAX_PARALLEL_FETCHES = 5

# Newest-first cap for the RM Discussion tab (one row per session).
DEFAULT_DISCUSSION_LIMIT = 20


# ---------------------------------------------------------------------------
# Row normalization
# ---------------------------------------------------------------------------

def _normalize_value(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key.lower(): _normalize_value(val) for key, val in row.items()}


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _fetch_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Run one SELECT on a pooled connection, return normalized dict rows."""
    with closing(get_db_connection()) as conn:
        with closing(conn.cursor(dictionary=True)) as cur:
            cur.execute(query, params)
            return [_normalize_row(row) for row in cur.fetchall()]


def _fetch_one(query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    rows = _fetch_all(query, params)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Chat path: guarded execution of validated LLM-generated SQL
# ---------------------------------------------------------------------------

CHAT_QUERY_TIMEOUT_SECONDS = 10


def execute_readonly_sql(query: str,
                         timeout_seconds: int = CHAT_QUERY_TIMEOUT_SECONDS) -> List[Dict[str, Any]]:
    """
    Execute one ALREADY-VALIDATED chat query (src/sql_guardrails.py must
    have passed it first — this function does not re-validate).

    Defense in depth at the session level regardless of validation:
    - the session is forced READ ONLY, so any write that slipped through
      fails at the engine;
    - a statement timeout is set (MariaDB max_statement_time / MySQL
      MAX_EXECUTION_TIME — whichever the server accepts);
    - runs on the read-only pool (dedicated SELECT-only credentials when
      DB_RO_USER is configured).
    """
    with closing(get_readonly_db_connection()) as conn:
        with closing(conn.cursor(dictionary=True)) as cur:
            for stmt in (
                f"SET SESSION max_statement_time={timeout_seconds}",           # MariaDB (seconds)
                f"SET SESSION MAX_EXECUTION_TIME={timeout_seconds * 1000}",    # MySQL (ms)
            ):
                try:
                    cur.execute(stmt)
                except Exception:
                    pass  # whichever variant the engine doesn't know
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.execute(query)
            return [_normalize_row(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Code resolution (CLIENT_MASTER / RM_MASTER / CLIENT_RM_MAPPING)
# ---------------------------------------------------------------------------

def fetch_client(client_code: str) -> Optional[Dict[str, Any]]:
    """CLIENT_MASTER row for the code, or None if the client doesn't exist."""
    return _fetch_one(
        "SELECT * FROM CLIENT_MASTER WHERE APR_CLIENT_CODE = %s",
        (client_code,),
    )


def fetch_rm(rm_code: str) -> Optional[Dict[str, Any]]:
    """RM_MASTER row for the code, or None if the RM doesn't exist."""
    return _fetch_one(
        "SELECT * FROM RM_MASTER WHERE RM_CODE = %s",
        (rm_code,),
    )


def fetch_rm_clients(rm_code: str) -> List[Dict[str, Any]]:
    """
    Clients actively mapped to an RM (MAPPING_END_DATE IS NULL), primary
    mappings first — the option list for the RM-search client picker.
    """
    return _fetch_all(
        """
        SELECT
            M.APR_CLIENT_CODE,
            C.CLIENT_NAME,
            C.CLIENT_SEGMENT,
            C.CLIENT_STATUS,
            M.MAPPING_ROLE,
            M.IS_PRIMARY,
            M.MAPPING_START_DATE
        FROM CLIENT_RM_MAPPING M
        JOIN CLIENT_MASTER C ON C.APR_CLIENT_CODE = M.APR_CLIENT_CODE
        WHERE M.RM_CODE = %s
          AND M.MAPPING_END_DATE IS NULL
        ORDER BY M.IS_PRIMARY DESC, C.CLIENT_NAME
        """,
        (rm_code,),
    )


def resolve_lookup_code(code: str, code_type: str) -> Dict[str, Any]:
    """
    Resolve a sidebar lookup code against the masters.

    Args:
        code: formatted code (src.utils.format_client_code output)
        code_type: "APR_CLIENT_CODE" or "RM_CODE"
                   (src.utils.validate_client_code output)

    Returns:
        {"code_type": "APR_CLIENT_CODE", "client": {...} | None}
        or
        {"code_type": "RM_CODE", "rm": {...} | None, "clients": [...]}

    A None client/rm means the code is well-formed but unknown — the app
    must show "not found" instead of proceeding (no more LLM-invented
    clients). For RM_CODE, "clients" feeds the client picker; each entry's
    apr_client_code is then used for fetch_all_tab_data().
    """
    if code_type == "RM_CODE":
        rm = fetch_rm(code)
        return {
            "code_type": "RM_CODE",
            "rm": rm,
            "clients": fetch_rm_clients(code) if rm else [],
        }
    return {
        "code_type": "APR_CLIENT_CODE",
        "client": fetch_client(code),
    }


# ---------------------------------------------------------------------------
# Per-tab summary fetches (one view each; see DB-Design-Schema/Views/)
# ---------------------------------------------------------------------------

def fetch_cms_summary(client_code: str) -> Optional[Dict[str, Any]]:
    return _fetch_one(
        "SELECT * FROM VW_CMS_SUMMARY WHERE APR_CLIENT_CODE = %s",
        (client_code,),
    )


def fetch_rm_details_summary(client_code: str) -> Optional[Dict[str, Any]]:
    return _fetch_one(
        "SELECT * FROM VW_RM_DETAILS_SUMMARY WHERE APR_CLIENT_CODE = %s",
        (client_code,),
    )


def fetch_asset_base_summary(client_code: str) -> Optional[Dict[str, Any]]:
    return _fetch_one(
        "SELECT * FROM VW_ASSET_BASE_SUMMARY WHERE APR_CLIENT_CODE = %s",
        (client_code,),
    )


def fetch_liability_base_summary(client_code: str) -> Optional[Dict[str, Any]]:
    return _fetch_one(
        "SELECT * FROM VW_LIABILITY_BASE_SUMMARY WHERE APR_CLIENT_CODE = %s",
        (client_code,),
    )


def fetch_product_holdings_summary(client_code: str) -> Optional[Dict[str, Any]]:
    return _fetch_one(
        "SELECT * FROM VW_PRODUCT_HOLDINGS_SUMMARY WHERE APR_CLIENT_CODE = %s",
        (client_code,),
    )


def fetch_rm_discussion_sessions(
    client_code: str, limit: int = DEFAULT_DISCUSSION_LIMIT
) -> List[Dict[str, Any]]:
    """One row per discussion session, newest first (see Views/README.md —
    this is the one view whose grain is not one-row-per-client)."""
    return _fetch_all(
        """
        SELECT * FROM VW_RM_DISCUSSION_SUMMARY
        WHERE APR_CLIENT_CODE = %s
        ORDER BY DISCUSSION_DATE DESC
        LIMIT %s
        """,
        (client_code, limit),
    )


# ---------------------------------------------------------------------------
# Chart fetches (feed src/chart_generator.py's six charts)
# ---------------------------------------------------------------------------

def fetch_asset_charts_data(client_code: str) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "category_breakdown": _fetch_all(
            """
            SELECT ASSET_CATEGORY, CATEGORY_VALUE
            FROM VW_ASSET_CATEGORY_BREAKDOWN
            WHERE APR_CLIENT_CODE = %s
            ORDER BY CATEGORY_VALUE DESC
            """,
            (client_code,),
        ),
        "quality_distribution": _fetch_all(
            """
            SELECT ASSET_CLASSIFICATION, OUTSTANDING_VALUE, PERCENTAGE_OF_TOTAL
            FROM VW_ASSET_QUALITY_DISTRIBUTION
            WHERE APR_CLIENT_CODE = %s
            ORDER BY OUTSTANDING_VALUE DESC
            """,
            (client_code,),
        ),
        "growth_trend": _fetch_all(
            """
            SELECT TREND_YEAR, TREND_MONTH, TOTAL_ASSET_VALUE
            FROM VW_ASSET_GROWTH_TREND
            WHERE APR_CLIENT_CODE = %s
            ORDER BY TREND_YEAR, TREND_MONTH
            """,
            (client_code,),
        ),
    }


def fetch_liability_charts_data(client_code: str) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "category_breakdown": _fetch_all(
            """
            SELECT LIABILITY_CATEGORY, CATEGORY_VALUE
            FROM VW_LIABILITY_CATEGORY_BREAKDOWN
            WHERE APR_CLIENT_CODE = %s
            ORDER BY CATEGORY_VALUE DESC
            """,
            (client_code,),
        ),
        "maturity_profile": _fetch_all(
            """
            SELECT LIABILITY_CATEGORY, MATURITY_BUCKET, BUCKET_TOTAL
            FROM VW_LIABILITY_MATURITY_PROFILE
            WHERE APR_CLIENT_CODE = %s
            ORDER BY LIABILITY_CATEGORY, MATURITY_BUCKET
            """,
            (client_code,),
        ),
        "rate_exposure": _fetch_all(
            """
            SELECT RATE_BUCKET, BUCKET_VALUE
            FROM VW_LIABILITY_RATE_EXPOSURE
            WHERE APR_CLIENT_CODE = %s
            ORDER BY BUCKET_VALUE DESC
            """,
            (client_code,),
        ),
    }


# ---------------------------------------------------------------------------
# Parallel fetch of everything a client dashboard needs
# ---------------------------------------------------------------------------

def fetch_all_tab_data(client_code: str) -> Dict[str, Any]:
    """
    Fetch every tab's summary rows and both chart bundles for one client,
    in parallel (tabs are independent — CLAUDE.md's parallelization lever).

    Returns a dict keyed for the narration layer:
        apr_client_code, client, cms_summary, rm_details_summary,
        asset_base_summary, liability_base_summary,
        product_holdings_summary, rm_discussion_sessions,
        asset_charts, liability_charts

    Raises ValueError if the client doesn't exist in CLIENT_MASTER, so an
    unknown code can never reach the LLM narration step.
    """
    client = fetch_client(client_code)
    if client is None:
        raise ValueError(f"Unknown APR_CLIENT_CODE: {client_code}")

    fetchers = {
        "cms_summary": fetch_cms_summary,
        "rm_details_summary": fetch_rm_details_summary,
        "asset_base_summary": fetch_asset_base_summary,
        "liability_base_summary": fetch_liability_base_summary,
        "product_holdings_summary": fetch_product_holdings_summary,
        "rm_discussion_sessions": fetch_rm_discussion_sessions,
        "asset_charts": fetch_asset_charts_data,
        "liability_charts": fetch_liability_charts_data,
    }

    result: Dict[str, Any] = {
        "apr_client_code": client_code,
        "client": client,
    }
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_FETCHES) as pool:
        futures = {
            key: pool.submit(fetch_fn, client_code)
            for key, fetch_fn in fetchers.items()
        }
        for key, future in futures.items():
            result[key] = future.result()
    return result
