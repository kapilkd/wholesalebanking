# CLAUDE.md

Guidance for Claude Code (and future contributors) working in this repository.

## What this project is

A Streamlit-based wholesale banking chatbot/dashboard. A user submits a
client identifier (`APR_CLIENT_CODE`, 8-14 chars, e.g. `APR12345678`, or
`RM_CODE`, 6-7 chars) and the app renders 5 tabs of client information plus a
free-form chat assistant.

## Current state — important caveat

**Every number and sentence the app currently shows is LLM-hallucinated.**
There is no database anywhere in this repo. `src/multi_agent_generator.py`
runs a 5-agent LangGraph chain (`app.py` → `MultiAgentSummaryGenerator`)
where each agent's prompt literally asks GPT-4 to *"generate a comprehensive
dummy summary"* with invented RM names, asset values, product holdings, etc.
`src/chart_generator.py`'s charts are hardcoded static arrays that ignore the
`client_code` argument entirely.

This is a working prototype of the **UI and orchestration shape**, not of the
data. The project's next major phase — described below — is to replace the
hallucinated content with real SQL-backed data, keeping the LLM's role
strictly limited to narrating retrieved facts.

## Repository structure

```
Wholesale_banking/
├── app.py                          # Streamlit UI: sidebar client lookup, 5 tabs, chat
├── config/
│   ├── langchain_config.py         # get_llm() factory (OpenAI via LangChain)
│   └── db_config.py                # MySQL/MariaDB pooled connection factory (DB_* env vars)
├── src/
│   ├── multi_agent_generator.py    # LangGraph 5-agent chain — currently 100% dummy-data generation
│   ├── chatbot.py                  # Free-form chat assistant (no DB, no structured context)
│   ├── chart_generator.py          # Plotly charts — currently hardcoded dummy data
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

The 5 UI tabs map 1:1 to `DB-Design-Schema` files 02-06 (`app.py` doesn't yet
have a CMS tab — CMS is a planned addition, already covered by
`01_CMS.sql`).

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

`src/chatbot.py` currently answers free-form questions with zero grounding
in real data. Classic vector-similarity RAG is the *wrong* tool here —
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

## Not yet implemented

- Rules layer (thresholds/filters between SQL fetch and LLM narration).
- Rewiring `src/multi_agent_generator.py` to narrate `db_reader` payloads
  (low temperature) instead of inventing data.
- Wiring `src/chart_generator.py` to `db_reader`'s chart data instead of
  hardcoded arrays.
- RM-search client-picker UX in `app.py` (data side exists in `db_reader`).
- NL2SQL schema catalog / vector store for the chat assistant.
- A CMS tab in `app.py` (schema exists in `01_CMS.sql`, UI does not yet).
