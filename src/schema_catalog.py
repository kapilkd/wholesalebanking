"""
Schema metadata catalog for the chat assistant's NL2SQL step.

Parses the design-source DDL in DB-Design-Schema/*.sql (NOT the live
database) into one document per table: name, business domain (from the
file it lives in), description (the comment banner above CREATE TABLE),
columns with types + inline business-meaning comments, and FK references.

Per CLAUDE.md's chat-path design, it is this CATALOG that gets embedded /
retrieved — never row data. The catalog is deterministic and cheap to
build, so it's parsed fresh at process start and cached in-memory.
"""
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "DB-Design-Schema"

# filename -> human-readable business domain
DOMAIN_BY_FILE = {
    "00_Master_Tables.sql": "Shared masters (clients, RMs, branches, products, accounts)",
    "01_CMS.sql": "Customer management: profiles, contacts, communications, calls, meetings, documents, balances",
    "02_Asset_Base.sql": "Asset base: loans, trade finance, investments, securities, collateral, NPA classification, limits",
    "03_Liability_Base.sql": "Liability base: term deposits, current accounts, borrowings, bonds, maturities, interest rates",
    "04_Product_Holdings.sql": "Product holdings: cross-product summary, utilization, cross-sell, fee income, channels",
    "05_RM_Details_Interactions.sql": "RM performance, interaction rollups, visit plans, escalations, targets, feedback",
    "06_RM_Discussion.sql": "RM-client discussion sessions, topics, needs, proposed solutions, follow-ups, outcomes",
}

_CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE (\w+) \((.*?)^\);", re.DOTALL | re.MULTILINE
)
_COLUMN_RE = re.compile(
    r"^\s{4}(\w+)\s+([A-Z]+(?:\(\d+(?:,\d+)?\))?)"      # name, type
    r"(?P<rest>[^,\n]*(?:,)?[^\n]*)$"                    # remainder of the line
)
_REFERENCES_RE = re.compile(r"REFERENCES\s+(\w+)\s*\((\w+)\)")
_INLINE_COMMENT_RE = re.compile(r"--\s*(.+)$")


def _table_description(sql_text: str, table_start: int) -> str:
    """The `-- ...` banner lines immediately above CREATE TABLE."""
    lines = sql_text[:table_start].rstrip().splitlines()
    desc: List[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped.startswith("--"):
            break
        text = stripped.lstrip("-").strip()
        if text and not set(text) <= {"-", "="}:
            desc.append(text)
    return " ".join(reversed(desc))


def _parse_columns(body: str) -> List[Dict]:
    columns = []
    for line in body.splitlines():
        m = _COLUMN_RE.match(line)
        if not m:
            continue
        name, col_type = m.group(1), m.group(2)
        if name in ("PRIMARY", "FOREIGN", "CONSTRAINT", "UNIQUE", "CHECK"):
            continue
        rest = m.group("rest") or ""
        ref = _REFERENCES_RE.search(rest)
        comment = _INLINE_COMMENT_RE.search(line)
        columns.append({
            "name": name,
            "type": col_type,
            "comment": comment.group(1).strip() if comment else "",
            "references": f"{ref.group(1)}.{ref.group(2)}" if ref else "",
        })
    return columns


@lru_cache(maxsize=1)
def build_catalog() -> tuple:
    """
    Parse every DB-Design-Schema/0*.sql into table documents.

    Returns a tuple (hashable for caching) of dicts:
        {table, domain, description, columns: [...], client_scoped: bool}
    """
    docs = []
    for filename, domain in DOMAIN_BY_FILE.items():
        sql_text = (SCHEMA_DIR / filename).read_text(encoding="utf-8")
        for m in _CREATE_TABLE_RE.finditer(sql_text):
            table, body = m.group(1), m.group(2)
            columns = _parse_columns(body)
            docs.append({
                "table": table,
                "domain": domain,
                "description": _table_description(sql_text, m.start()),
                "columns": columns,
                "client_scoped": any(c["name"] == "APR_CLIENT_CODE" for c in columns),
            })
    return tuple(docs)


def catalog_tables() -> List[str]:
    return [doc["table"] for doc in build_catalog()]


def render_table_doc(doc: Dict) -> str:
    """One table as flat text — the unit that gets embedded / shown to the LLM."""
    col_lines = []
    for c in doc["columns"]:
        parts = [f"{c['name']} {c['type']}"]
        if c["references"]:
            parts.append(f"references {c['references']}")
        if c["comment"]:
            parts.append(c["comment"])
        col_lines.append(" — ".join(parts))
    scope = "client-scoped via APR_CLIENT_CODE" if doc["client_scoped"] else "reference/master table"
    return (
        f"TABLE {doc['table']} ({scope})\n"
        f"Domain: {doc['domain']}\n"
        f"Description: {doc['description']}\n"
        "Columns:\n  " + "\n  ".join(col_lines)
    )
