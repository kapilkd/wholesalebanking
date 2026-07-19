# CLAUDE.md

Guidance for Claude Code (and future contributors) working in this repository.

## What this project is

A Streamlit-based wholesale banking chatbot/dashboard. A user submits a
client identifier (`APR_CLIENT_CODE`, 8-14 chars, e.g. `APR12345678`, or
`RM_CODE`, 6-7 chars) and the app renders 6 tabs of client information plus a
free-form chat assistant.

## Current state

The app is fully DB-backed end to end: tab content is narrated from rows
fetched deterministically out of the `wholesale` MySQL/MariaDB database
(never invented), charts render real view rows, RM search resolves to a
client picker, and the chat assistant answers data questions through a
guarded NL2SQL pipeline, and a deterministic rules layer decides what the
narration emphasizes. See "Implemented so far" below for the module map —
the designed architecture is fully implemented.

## Repository structure

```
Wholesale_banking/
├── app.py                          # Streamlit UI: sidebar client lookup, 6 tabs, chat
├── config/
│   ├── langchain_config.py         # get_llm() factory (OpenAI via LangChain)
│   └── db_config.py                # MySQL/MariaDB pooled connection factory (DB_* env vars)
├── src/
│   ├── multi_agent_generator.py    # LangGraph 6-agent parallel narration of db_reader payloads
│   ├── chatbot.py                  # Grounded chat: schema-RAG + NL2SQL pipeline
│   ├── schema_catalog.py           # DDL -> per-table metadata docs (chat path)
│   ├── schema_retriever.py         # Schema-slice retrieval (embeddings / lexical)
│   ├── sql_guardrails.py           # sqlglot validation of generated SQL
│   ├── rules_layer.py              # Deterministic thresholds/top-N/date-window highlights
│   ├── summary_cache.py            # In-process TTL+LRU cache for generated dashboards
│   ├── chart_generator.py          # Plotly charts built from db_reader chart-view payloads
│   ├── db_reader.py                # Deterministic view-fetch layer + client/RM code resolution
│   └── utils.py                    # client code validation/formatting
├── scripts/
│   └── seed_data.py                # One-shot seed for the `wholesale` DB (~250 clients)
├── DB-Design-Schema/                # Proposed SQL schema — see below
│   ├── README.md                    # Index + conventions + cross-file relationship map
│   ├── 00_Master_Tables.sql         # Shared masters (client, RM, branch, currency, product, ...)
│   ├── 01_CMS.sql                   # Customer info, comms, calls, meetings, docs, balances
│   ├── 02_Asset_Base.sql            # Loans, trade finance, investments, securities, NPA, history
│   ├── 03_Liability_Base.sql        # Deposits, current accounts, borrowings, bonds, history
│   ├── 04_Product_Holdings.sql      # Cross-product holdings, utilization, cross-sell
│   ├── 05_RM_Details_Interactions.sql
│   ├── 06_RM_Discussion.sql
│   └── Views/                       # CREATE VIEW layer — one summary view per tab + chart views
│       ├── README.md                # Query pattern, chart mapping, view design principles
│       └── 01_CMS_Views.sql ... 06_RM_Discussion_Views.sql
├── PROJECT_SUMMARY.md               # Deep-dive on the current (dummy-data) architecture
├── UI_STRUCTURE_CHANGES.md
└── requirements.txt                 # incl. mysql-connector-python (DB driver)
```

The 6 UI tabs map 1:1 to `DB-Design-Schema` files 01-06 (CMS first).

## Target architecture: the SQL flow

This is the design direction agreed for moving the app off hallucinated
content. It has two genuinely different retrieval patterns — don't conflate
them.

### 1. Tab rendering — deterministic, no LLM in the data path

Each tab already knows what data it needs. The flow is a strict pipeline,
and only the last step touches the LLM:

```
CREATE VIEW per tab (joins the tab's tables, filtered by APR_CLIENT_CODE)
        │  — pure SQL, does all aggregation in the DB, not in Python/LLM
        ▼
Rules layer (Python/SQL: thresholds, active/inactive, top-N, date windows)
        │  — deterministic, auditable, decides WHAT gets shown
        ▼
LLM narration (low temperature, e.g. 0.1-0.2)
        │  — given ONLY the filtered structured rows as context
        │  — instructed: summarize only these numbers, never invent any
        ▼
Rendered tab content
```

This replaces every `generate_*_summary` method in
`src/multi_agent_generator.py`. The LLM stops being the data source and
becomes a narrator. No tool-calling / agentic loop belongs in this path —
the query is already known, so an agent loop would only add latency and
nondeterminism for zero benefit. Tabs are independent, so their SQL fetches
should run in parallel (LangGraph parallel branches, or plain
`asyncio`/thread pool) rather than the current fully sequential chain.

**Views are built**: `DB-Design-Schema/Views/` — one `VW_<TAB>_SUMMARY` view
per tab (one row per client; `VW_RM_DISCUSSION_SUMMARY` is the one exception,
one row per discussion session), plus `VW_ASSET_CATEGORY_BREAKDOWN` /
`VW_ASSET_QUALITY_DISTRIBUTION` / `VW_ASSET_GROWTH_TREND` and
`VW_LIABILITY_CATEGORY_BREAKDOWN` / `VW_LIABILITY_MATURITY_PROFILE` /
`VW_LIABILITY_RATE_EXPOSURE` — chart-shaped views feeding
`src/chart_generator.py`'s six charts directly. Views take no parameters;
query with `WHERE APR_CLIENT_CODE = ?`. See `DB-Design-Schema/Views/README.md`.

### 2. The chat assistant — schema-RAG + NL2SQL

(Implemented — see "Implemented so far". Design rationale kept below.)
Classic vector-similarity RAG is the *wrong* tool here —
banking numbers need to be exactly right, not semantically similar. The
correct pattern:

1. Build a metadata catalog (table name, columns, business meaning, join
   keys) describing every table across `DB-Design-Schema/*.sql`.
2. Embed that catalog — **not the row data** — into a vector store. This is
   where "RAG" actually applies: retrieving the 5-10 relevant tables/columns
   for a given question.
3. Feed the retrieved schema slice + few-shot examples to a constrained
   NL2SQL generation step.
4. Validate the generated SQL before running it (see guardrails below).
5. Execute, then have the LLM narrate the *returned rows* — same
   "LLM narrates, never invents" rule as the tab path.

### SQL-only orchestration constraint

Per project decision: the LLM/agent layer must never take any action other
than running SQL against the database — no other tools, no free code
execution, no web access.

- **Tab path**: no LLM tool access at all. SQL is fetched deterministically
  in application code; the LLM only ever receives already-fetched rows as
  context and returns prose.
- **Chat path**: exactly one tool exposed to the LLM,
  `execute_readonly_sql(query)`. Guardrails, all mandatory:
  - Parse generated SQL (e.g. `sqlglot`) — reject anything that isn't a
    single `SELECT`; reject multiple statements; reject DDL/DML keywords.
  - Enforce a table/column allow-list built from the retrieved schema slice.
  - Force a `LIMIT`; enforce a query timeout (5-10s).
  - Run against a read-only DB role, ideally a read replica — never the
    primary transactional connection.

### Performance characteristics / execution time estimate

Every transactional table in `DB-Design-Schema/*.sql` carries `APR_CLIENT_CODE`
with a leading index specifically for this reason: every real query this app
runs is client-scoped, so a well-indexed join returns a tiny result set
regardless of how large the underlying tables are.

| Stage | Well-indexed | Poorly indexed |
|---|---|---|
| Per-tab SQL (10-20 table join, filtered by client) | 50-300ms | 5-30s+ |
| All tabs' SQL, run in parallel | ~1-3s (bounded by slowest) | dominates everything |
| LLM narration per tab | 2-5s | same |
| All tab narrations, parallel | ~3-6s | same |
| **Total, parallelized design** | **~5-10s** | highly variable |
| Total, current sequential design (5 LLM calls back to back) | ~20-30s (matches `PROJECT_SUMMARY.md`'s own estimate) | worse |
| Chat: schema retrieval + NL2SQL + execution + narration | ~3-8s typical | up to ~15s on complex joins |

Biggest lever by far: indexing on `APR_CLIENT_CODE` / join keys and pushing
aggregation into the DB (already reflected in the schema design). Second:
parallelizing the currently-sequential LangGraph chain. Third: caching
(Redis or a timestamped cache keyed by client code) for repeat views.

## Conventions

- **SQL**: `UPPER_SNAKE_CASE`, domain-prefixed tables (`CMS_`, `ASSET_`,
  `LIABILITY_`, `PRODUCT_`, `RM_`), portable ANSI SQL (no engine-specific
  syntax — see `DB-Design-Schema/README.md`).
- **Python**: `lower_snake_case` dict keys for LLM payloads (matches existing
  `SummaryState` TypedDict in `src/multi_agent_generator.py`).
- **Masters are defined once**: only in `DB-Design-Schema/00_Master_Tables.sql`,
  referenced by FK elsewhere — never redefined.
- **One tab, one file**: `DB-Design-Schema/*.sql` files never mix tab-specific
  tables; shared data lives in the masters file only.

## Implemented so far (data path)

- **Engine chosen: MySQL/MariaDB.** `config/db_config.py` provides a pooled
  connection factory from `DB_*` env vars (see `.env.example`);
  `DB-Design-Schema/MySQL_Deploy/` holds the engine-ready DDL;
  `scripts/seed_data.py` seeds a moderate-volume `wholesale` database.
- **`src/db_reader.py`** — the deterministic fetch layer:
  `resolve_lookup_code()` validates an `APR_CLIENT_CODE` against
  `CLIENT_MASTER` (unknown code → not-found, never an LLM guess) or resolves
  an `RM_CODE` via `CLIENT_RM_MAPPING` to the RM's actively-mapped clients
  (feeds the RM-search **client picker** — tab views are keyed by client
  code only); `fetch_all_tab_data()` fetches every tab summary view plus all
  six chart views in parallel and returns one JSON-safe,
  `lower_snake_case` payload for the rules/narration steps.
- **`src/multi_agent_generator.py` narrates DB payloads.** The 6 tab agents
  (incl. CMS)
  fan out in parallel from LangGraph `START` (partial state updates), each
  receiving only its tab's `db_reader` rows as JSON at temperature 0.1 under
  a strict never-invent narrator prompt. `generate_all_summaries()` keeps
  its old return keys (UI unchanged) and adds `tab_data` so charts/rules can
  reuse the fetch. Unknown codes raise `ValueError` before any LLM call;
  `app.py` shows not-found.
- **RM-search client picker in `app.py`.** Submitting an `RM_CODE` resolves
  via `db_reader.resolve_lookup_code()` to the RM's actively-mapped clients:
  sidebar shows an RM card + client selectbox + load button, main area shows
  an HTML overview table of the mapped clients (deliberately not
  `st.dataframe` — see the `use_pure` note in `config/db_config.py`; the
  picker table avoids Streamlit's pyarrow serialization path entirely).
  Loading a picked client runs the normal client dashboard flow
  (`load_client_dashboard()`), keeping the RM context chip; direct
  APR-code lookups clear picker state.

- **`src/chart_generator.py` renders `db_reader` chart payloads.** All six
  charts take the `tab_data["asset_charts"]` / `tab_data["liability_charts"]`
  rows fetched by `fetch_all_tab_data()` (`app.py` passes them through from
  the summaries result — no refetch), with fixed bucket ordering matching
  the seeded `MATURITY_BUCKET`/`RATE_BUCKET` labels and "No data available"
  placeholders for empty row sets.

- **Chat assistant is grounded (schema-RAG + NL2SQL).** `src/chatbot.py`
  runs the strict pipeline: `src/schema_catalog.py` parses the design-source
  DDL into per-table docs (74 tables: columns, comments, FK references);
  `src/schema_retriever.py` retrieves the relevant slice (OpenAI embeddings
  when a key is set, lexical fallback otherwise; always FK-closure + master
  tables); SQL is generated at temperature 0, validated by
  `src/sql_guardrails.py` (sqlglot: single SELECT only, table allow-list
  from the slice, forced/clamped LIMIT), executed via
  `db_reader.execute_readonly_sql()` (session forced READ ONLY, statement
  timeout, optional `DB_RO_*` SELECT-only credentials), then the returned
  rows are narrated under never-invent rules. One corrective retry on
  failure, then a graceful refusal. General product questions bypass the DB
  (`NO_QUERY`) but are forbidden from stating client figures.

- **Rules layer between fetch and narration.** `src/rules_layer.py` runs
  deterministic, threshold-driven rules over the fetched payload
  (`RULES_CONFIG` holds every tunable in one place): NPA share, limit
  utilization, covenant breaches, concentration risk, near-term maturities,
  stale contact, expired documents, open escalations, low feedback,
  cross-sell potential. Each finding is an auditable
  `{rule, severity, message}` highlight the narrator must weave in
  verbatim-in-substance; narration inputs are windowed (12-month growth
  trend, 180-day/10-session discussion cap with a stale fallback) while
  chart/UI payloads stay untouched. `generate_all_summaries()` returns the
  rules output under `"rules"`, and `app.py` renders it: per-tab severity
  badges (`render_highlight_badges()`) above each summary plus a
  warning-count "attention items" chip in the status row.
- **Repeat lookups are cached.** `src/summary_cache.py` (thread-safe,
  TTL via `SUMMARY_CACHE_TTL_SECONDS` default 600s, LRU-capped) stores the
  full `generate_all_summaries()` result per client; repeat lookups skip
  fetch + narration entirely. Results carry `generated_at`, shown as a
  freshness chip; the sidebar "Refresh data" button invalidates the entry
  and regenerates. Unknown codes are never cached.
