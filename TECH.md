# TECH.md — How the Wholesale Banking app actually works

This is the engineering deep-dive: module-by-module flow, how LangChain/
LangGraph agents are wired, how the chat assistant "searches" (and what that
word does and doesn't mean here), the database structure, and exactly how a
number on screen traces back to a row in MySQL. `CLAUDE.md` is the design
brief / roadmap; this file describes the system as built.

## 1. The big picture

There are **two independent pipelines**, and the most important architectural
fact about this app is that they don't share a code path:

```
TAB DASHBOARD (deterministic, no agent, no tool-calling)
    CREATE VIEW (MySQL)  →  db_reader.py  →  rules_layer.py  →  multi_agent_generator.py (LangGraph)  →  app.py

CHAT ASSISTANT (schema-RAG + NL2SQL, one tool call max)
    schema_retriever.py  →  chatbot.py (LLM writes SQL)  →  sql_guardrails.py  →  db_reader.execute_readonly_sql()  →  chatbot.py (LLM narrates rows)
```

The tab dashboard **never lets an LLM decide what to query** — the six SQL
views are fixed, always run, every time. The chat assistant is the only place
an LLM writes SQL, and every query it writes passes through a validator
before it's allowed to touch the database. This split is a deliberate
constraint from `CLAUDE.md` ("SQL-only orchestration"), not an accident of
how the code evolved.

## 2. Tab dashboard pipeline, step by step

Triggered by `app.py`'s `load_client_dashboard(client_code)`, which calls
`MultiAgentSummaryGenerator().generate_all_summaries(client_code)`.

### Step 1 — Cache check (`src/summary_cache.py`)

Before touching the database, `generate_all_summaries()` checks an
in-process, thread-safe, TTL+LRU cache keyed by `APR_CLIENT_CODE`
(`SUMMARY_CACHE_TTL_SECONDS`, default 600s; 64-entry cap). A hit returns the
entire previous result — summaries, chart data, rules output, generated-at
timestamp — with zero DB or LLM cost. This is why flipping between a few
clients repeatedly feels instant after the first load. The sidebar's
**Refresh data** button calls `summary_cache.invalidate(client_code)` to
force a real re-fetch.

### Step 2 — Deterministic SQL fetch (`src/db_reader.py`)

`fetch_all_tab_data(client_code)`:
1. Looks up `CLIENT_MASTER` for the code. **If it doesn't exist, raises
   `ValueError` immediately** — this is the single most important line in
   the app, because it means an unknown client code can *never* reach an
   LLM. There's nothing for the model to hallucinate around; the pipeline
   stops before it starts.
2. Otherwise, fires off **8 queries in parallel** via a `ThreadPoolExecutor`
   (5 workers, matching the DB connection pool size in
   `config/db_config.py`): one `SELECT * FROM VW_<TAB>_SUMMARY WHERE
   APR_CLIENT_CODE = %s` per tab (CMS, RM Details, Asset Base, Liability
   Base, Product Holdings), one windowed query against
   `VW_RM_DISCUSSION_SUMMARY` (this view is the one exception to "one row
   per client" — it's one row per discussion session), and two bundles of
   chart queries (`fetch_asset_charts_data`, `fetch_liability_charts_data`)
   against the 6 chart views.
3. Every row is normalized on the way out: `decimal.Decimal → float`,
   `date`/`datetime → ISO string`, all keys lowercased to
   `lower_snake_case`. This keeps the payload JSON-serializable (it gets
   dumped straight into LLM prompts) and consistent regardless of MySQL's
   native column casing.

The **views themselves** (`DB-Design-Schema/Views/*.sql`) do all the actual
joining and aggregation — see §6. `db_reader.py` never joins anything in
Python; it only ever does `SELECT * FROM VW_X WHERE APR_CLIENT_CODE = ?`.

### Step 3 — Rules layer (`src/rules_layer.py`)

Pure Python, no DB, no LLM. `apply_rules(tab_data)` runs a fixed set of
threshold checks against the fetched rows — every threshold lives in one
`RULES_CONFIG` dict (NPA share ≥5%, limit utilization ≥80%, stale contact
>60 days, concentration risk ≥40%, near-term maturity ≥50%, low feedback
<3.0, etc.) — and returns:

- **`highlights`**: per tab, a list of `{rule, severity, message}` findings.
  `severity` is `"warning"` or `"info"`. These are what `app.py` renders as
  the colored badge rows above each tab's narrative, and what the narrator
  prompt is told to weave into prose.
- **`narration_overrides`**: two pre-filtered row sets — the asset growth
  trend trimmed to the last 12 months, and RM Discussion sessions windowed
  to the last 180 days (capped at 10, with a "nothing recent, showing the
  latest anyway" fallback if the window is empty). These overrides apply
  **only to what the LLM sees in its narration prompt** — the charts and any
  future raw-data UI still get the full, untouched fetch from step 2.

This is the layer `CLAUDE.md` calls out as deciding *what deserves
attention*, deterministically and auditably, so that emphasis in the
narrative isn't an LLM's judgment call — it's a reproducible function of the
data.

### Step 4 — LangGraph narration (`src/multi_agent_generator.py`)

This is the only step that calls an LLM, and it never calls a tool — it
receives a JSON blob and returns prose. In detail:

- **Graph shape**: a LangGraph `StateGraph(SummaryState)` with **six nodes**
  (`cms_agent`, `rm_agent`, `asset_agent`, `liability_agent`, `product_agent`,
  `discussion_agent`), each wired `START → node → END`. Because every node
  hangs directly off `START` with no edges between nodes, LangGraph executes
  all six **concurrently** — this is the "5-call sequential chain" from the
  original prototype replaced with a real parallel fan-out, per the
  performance section of `CLAUDE.md`.
- **`SummaryState`** (a `TypedDict`) is the shared state object: it holds the
  input (`client_code`, `tab_data`, `rules`) and six string slots
  (`cms_summary`, `rm_summary`, ...). Each node function receives the full
  state and returns a **partial update dict** — e.g.
  `narrate_asset_summary` returns `{"asset_summary": "..."}` — which is
  LangGraph's required pattern for safely merging concurrent branches back
  into one state object.
- **Each node's job** is identical in shape: build a small payload dict from
  `tab_data` + that tab's `rules["highlights"]` (Asset additionally swaps in
  the rules-trimmed `growth_trend`; RM Discussion swaps in the
  rules-windowed `discussion_sessions` instead of the full fetch), then call
  the shared `_narrate(tab, coverage, payload)` helper.
- **`_narrate()`** sends exactly two messages to the LLM: a fixed
  `NARRATOR_SYSTEM_PROMPT` (the grounding rules, see below) and a
  `HumanMessage` containing the tab name, a one-line description of what to
  cover, and `json.dumps(payload)` — literally the rows from the database,
  nothing else. There is no retrieval, no tool call, no second turn.
- **Grounding rules** (`NARRATOR_SYSTEM_PROMPT`): use only facts present in
  the JSON; never invent/estimate/extrapolate; omit missing fields instead
  of guessing; state plainly when there's no data instead of describing
  activity that isn't there; format money as `₹**XX.XX CR**`; weave in every
  rules-layer highlight without contradicting it. Temperature is **0.1**
  (`NARRATION_TEMPERATURE`) — CLAUDE.md prescribes 0.1–0.2 for this path
  specifically because narration needs to be deterministic prose over fixed
  numbers, not creative writing.
- **`generate_all_summaries()`** ties it together: cache check → `db_reader`
  fetch → `rules_layer.apply_rules()` → build `initial_state` → `graph.invoke()`
  (blocks until all 6 branches finish) → assemble the result dict (6
  summary strings + `tab_data` + `rules` + `generated_at` timestamp) → store
  in the cache → return.

### Step 5 — Rendering (`app.py`)

`st.session_state.client_summaries` holds the whole result. Each tab reads
its summary string straight into a styled `<div class="summary-text">`, and
calls `render_highlight_badges(tab_key)` first to render that tab's
`rules["highlights"]` as colored badges. Asset Base and Liability Base
additionally pull `tab_data["asset_charts"]` / `["liability_charts"]` and
pass them to `ChartGenerator` (§7). Nothing in `app.py`'s render path talks
to the database or an LLM directly — it only reads out of the
already-assembled dict.

## 3. Chat assistant pipeline, step by step

`src/chatbot.py`'s `WholesaleBankingChatbot.get_response(question)`. Unlike
the tab path, this one **does** let an LLM decide what to query — so it gets
a validator between the LLM and the database, and nothing else.

1. **Schema retrieval** (`src/schema_retriever.py`) — see §4 for what this
   actually is. Returns 8–16ish table "documents" (name, columns, types,
   comments, FK references) relevant to the question, always including the
   FK-closure of whatever was picked plus `CLIENT_MASTER`, `RM_MASTER`,
   `CLIENT_RM_MAPPING`, `PRODUCT_MASTER`.
2. **SQL generation** (`chatbot._generate_sql`) — one LLM call at
   **temperature 0**, given the rendered schema slice, the current
   `APR_CLIENT_CODE` (if any), a short window of conversation history, and
   two few-shot examples. System prompt (`SQL_GENERATION_RULES`) constrains
   it to: exactly one `SELECT`, only tables/columns in the given slice,
   always filter client-scoped tables by the current client, aggregate
   rather than dump raw rows, always include a `LIMIT`. A question needing
   no data at all (e.g. "what's trade finance?") gets the literal sentinel
   `NO_QUERY` instead of SQL.
3. **Validation** (`src/sql_guardrails.py`) — `validate_sql()` parses the
   LLM's output with `sqlglot` (MySQL dialect) and rejects it unless **all**
   of: exactly one statement; that statement is a `SELECT` or `UNION` of
   `SELECT`s (any `INSERT`/`UPDATE`/`DELETE`/`DROP`/`ALTER`/`GRANT`/... node
   anywhere in the AST fails it, as does `SELECT ... INTO`); every table
   referenced (excluding CTE aliases) is on the retrieved allow-list. A
   missing `LIMIT` gets one appended (100 default); an oversized one gets
   clamped (500 max). Returns the sanitized SQL string, or raises
   `SQLValidationError` with a human-readable reason.
4. **Execution** (`db_reader.execute_readonly_sql()`) — runs the *already
   validated* SQL with three layers of defense-in-depth beyond the
   guardrail check itself: the session is forced `SET SESSION TRANSACTION
   READ ONLY` (so anything that slipped past validation still fails at the
   engine), a statement timeout is set (`max_statement_time` for MariaDB /
   `MAX_EXECUTION_TIME` for MySQL — both attempted, whichever the server
   understands wins), and it runs on a **separate connection pool**
   (`get_readonly_db_connection()`) that uses dedicated `DB_RO_USER` /
   `DB_RO_PASSWORD` credentials when configured, falling back to the
   primary credentials otherwise.
5. **Retry**: steps 2–4 get **one corrective retry** — if generation,
   validation, or execution fails, the error text is fed back into the next
   SQL-generation call ("your previous attempt failed with this error — fix
   it"). Two failures in a row → a plain-language refusal, never a guess.
6. **Narration** (`chatbot._narrate_rows`) — a second LLM call, temperature
   0.1, given the question, the exact SQL that ran, and the returned rows as
   JSON. Same never-invent grounding rules as the tab path. The rendered
   answer in the UI also appends the executed SQL in a `<sub>` tag for
   transparency.
7. **General questions** (`NO_QUERY`): answered directly by the narrator LLM
   under a separate system prompt that explicitly forbids stating any
   client-specific figure, since no rows were fetched for that turn.

Session-level bookkeeping: `WholesaleBankingChatbot` keeps
`conversation_history` (last 3 turns are stuffed into the SQL-generation
prompt for follow-up questions like "and what about last quarter?"), and
`update_client_code()` resets history when the sidebar client changes so an
old client's context doesn't leak into a new session.

## 4. What "search" means here — and what it deliberately doesn't

There is **no vector search over banking data anywhere in this app.**
Classic RAG (embed rows, retrieve by similarity) is explicitly the wrong
tool for numbers that have to be exactly right, not "semantically close." The
one place retrieval happens is choosing *which tables* the NL2SQL step is
allowed to see — retrieving schema, never rows.

- **`src/schema_catalog.py`** parses the design-source DDL — the human-
  authored files in `DB-Design-Schema/*.sql`, **not** a live introspection of
  the running database — into one document per table: name, business domain
  (derived from which file it lives in), the `--` comment banner above
  `CREATE TABLE` as a description, every column with its type + inline
  comment, and any `REFERENCES` as a foreign key. Regex-based, cached with
  `@lru_cache` (parsed once per process). Currently produces 74 table
  documents, matching the 74-table schema.
- **`src/schema_retriever.py`** has two interchangeable backends behind
  `get_retriever()`:
  - **`EmbeddingRetriever`** (used when `OPENAI_API_KEY` is set): embeds all
    74 rendered table documents once at startup with
    `text-embedding-3-small`, then does in-memory cosine similarity against
    the question's embedding. No vector database — 74 short documents fits
    entirely in memory, so a proper vector store would be overhead, not a
    feature.
  - **`KeywordRetriever`** (automatic fallback if no API key, or if
    embedding bootstrap throws): a dependency-free TF-IDF-flavored lexical
    scorer over table/column names (weighted 2x) and comments, with a naive
    plural-fold (`"loans"` → `"loan"`) so question phrasing loosely matches
    schema identifiers.
  - Either way, the result is completed by `_with_masters()`: one hop of
    FK-closure (if `ASSET_LOAN_DETAILS` is picked, its FK target
    `ASSET_ACCOUNT_MASTER` is pulled in too, since generated SQL will need
    to join through it) plus the always-included masters
    (`CLIENT_MASTER`, `RM_MASTER`, `CLIENT_RM_MAPPING`, `PRODUCT_MASTER`).

The output — rendered table docs via `render_table_doc()` — is what actually
gets pasted into the SQL-generation prompt in §3 step 2. This is the "RAG" in
this system: retrieval of *metadata*, feeding a *generation* step, same as
any RAG pipeline — just over a 74-document schema catalog instead of a
row-level corpus.

## 5. Module reference

| Module | Role | Talks to DB? | Talks to LLM? |
|---|---|---|---|
| `app.py` | Streamlit UI, session state, sidebar lookup, tab rendering, chat UI | No (all through `db_reader`/generators) | No |
| `src/db_reader.py` | Deterministic view fetches, code resolution, guarded chat-SQL execution | Yes (pooled) | No |
| `src/rules_layer.py` | Threshold-driven highlights + narration windowing | No | No |
| `src/multi_agent_generator.py` | LangGraph fan-out narrating `db_reader` payloads into 6 tab summaries | No (reads pre-fetched `tab_data`) | Yes (6 parallel calls, temp 0.1) |
| `src/chart_generator.py` | Builds all 6 Plotly figures from `db_reader` chart payloads | No | No |
| `src/summary_cache.py` | TTL+LRU in-process cache of full dashboard results | No | No |
| `src/chatbot.py` | Orchestrates the chat pipeline (§3) | No (delegates to `db_reader`) | Yes (SQL gen temp 0, narration temp 0.1) |
| `src/schema_catalog.py` | Parses `DB-Design-Schema/*.sql` into table metadata docs | No | No |
| `src/schema_retriever.py` | Retrieves relevant table docs for a question | No | Optional (embeddings only) |
| `src/sql_guardrails.py` | Validates/sanitizes LLM-generated SQL before execution | No | No |
| `src/utils.py` | `APR_CLIENT_CODE` / `RM_CODE` format validation | No | No |
| `config/db_config.py` | Pooled MySQL connections (primary + read-only) | Owns the pools | No |
| `config/langchain_config.py` | `get_llm()` factory (`ChatOpenAI`) | No | Owns the client |

## 6. Database structure

**Design source of truth**: `DB-Design-Schema/*.sql` (portable ANSI SQL, hand-
authored). **Deployed DDL**: `DB-Design-Schema/MySQL_Deploy/*.sql` (generated
from the design source — adds `AUTO_INCREMENT`, `ENGINE=InnoDB`, explicit
`TIMESTAMP` defaults, and explicit table-level `FOREIGN KEY` constraints,
since MySQL/MariaDB parses but silently does not enforce inline
column-level `REFERENCES`). Both describe the same 74 tables; only the deploy
version is what's actually loaded into the `wholesale` MariaDB instance
(`config/db_config.py`'s `DB_*` env vars point at it).

### Layout

```
00_Master_Tables.sql        8 tables  — CLIENT_MASTER, RM_MASTER, BRANCH_MASTER,
                                        CURRENCY_MASTER, SECTOR_MASTER, PRODUCT_MASTER,
                                        ACCOUNT_MASTER, CLIENT_RM_MAPPING
01_CMS.sql                 11 tables  — profile, address, contacts, comms/call/meeting
                                        logs, documents, balances (current + history),
                                        segment history, notes
02_Asset_Base.sql          20 tables  — loans, trade finance, investments, securities,
                                        collateral, NPA classification, sanction limits,
                                        covenants, guarantors, insurance, restructuring,
                                        write-offs
03_Liability_Base.sql      12 tables  — term deposits, current accounts, borrowings,
                                        bonds, maturity profile, interest rate history,
                                        risk metrics, renewals, closures
04_Product_Holdings.sql    10 tables  — cross-product summary, utilization, cross-sell,
                                        fee income, relationship depth, channel usage
05_RM_Details_Interactions.sql
                             7 tables — RM performance, interaction rollups, visit
                                        plans, escalations, targets, feedback
06_RM_Discussion.sql        6 tables  — discussion sessions, topics, needs, proposed
                                        solutions, follow-ups, outcomes
```

### Conventions that matter for how data flows

- **Every transactional table carries `APR_CLIENT_CODE` with a leading
  index.** This is *the* reason the deterministic view queries stay fast —
  the filter narrows to one client's rows before any join work happens,
  regardless of total table size. All of §7's execution-time estimates
  depend on this not being dropped.
- **Table-per-subclass pattern** (Asset Base, Liability Base): one
  `..._ACCOUNT_MASTER` header table per domain, plus a 1:1 detail table per
  category sharing the master's PK as its own PK/FK (e.g.
  `ASSET_LOAN_DETAILS`, `LIABILITY_TERM_DEPOSIT_DETAILS`). The header's
  `ASSET_CATEGORY` / `LIABILITY_CATEGORY` column says which single detail
  table to join. Detail-table PKs are *not* auto-increment — their value is
  copied from the parent at insert time.
- **Masters are defined exactly once**, only in `00_Master_Tables.sql`;
  every other file references them by FK, never redefines them.
- **Audit columns** (`CREATED_DATE`, `UPDATED_DATE`, `SOURCE_SYSTEM`) on
  every table, for traceability back to whatever core-banking system would
  feed it in a real deployment.
- **Monetary values are stored in INR Crores**, not raw rupees — every
  prompt and every chart label formats accordingly.

### The view layer (`DB-Design-Schema/Views/*.sql`)

12 views, deployed alongside the tables, are the *only* thing `db_reader.py`
queries — it never joins raw tables itself. Two grains:

- **Summary views** (one row per client): `VW_CMS_SUMMARY`,
  `VW_ASSET_BASE_SUMMARY`, `VW_LIABILITY_BASE_SUMMARY`,
  `VW_PRODUCT_HOLDINGS_SUMMARY`, `VW_RM_DETAILS_SUMMARY`. Each pre-aggregates
  every one-to-many child table (calls, meetings, disbursements, history
  rows) via a CTE *before* joining, so the client-grain row is never
  fanned out — a documented, deliberately-avoided bug class (see the views
  README's "no fan-out" rule).
- **Chart views** (multiple rows per client, one per category/bucket/month):
  `VW_ASSET_CATEGORY_BREAKDOWN`, `VW_ASSET_QUALITY_DISTRIBUTION`,
  `VW_ASSET_GROWTH_TREND`, `VW_LIABILITY_CATEGORY_BREAKDOWN`,
  `VW_LIABILITY_MATURITY_PROFILE`, `VW_LIABILITY_RATE_EXPOSURE`. These feed
  `ChartGenerator` directly.
- **The one exception**: `VW_RM_DISCUSSION_SUMMARY` is one row *per
  discussion session*, not per client — RM Discussion is inherently a list
  of qualitative events, not a single-row summary.

History tables use a **"latest snapshot"** pattern:
`ROW_NUMBER() OVER (PARTITION BY <account_id> ORDER BY <date_col> DESC) = 1`
in a CTE, rather than a correlated `MAX()` subquery — standard ANSI SQL:2003,
portable, and the pattern every "current balance" / "current rate" / "current
NPA classification" figure in the app traces back to.

## 7. Charts (`src/chart_generator.py`)

Six Plotly figures, built entirely from `tab_data["asset_charts"]` /
`["liability_charts"]` — the exact same fetch the narrator used, passed
through from `MultiAgentSummaryGenerator`'s result so `app.py` never
re-queries the database just to draw a chart. No LLM involvement at all;
this is pure Python/Plotly over already-fetched rows.

- **Asset**: category breakdown (bar), quality distribution (pie — the
  percentages come pre-computed from `VW_ASSET_QUALITY_DISTRIBUTION` and
  are verified to sum to 100), growth trend (line, last 12 months per the
  rules layer's narration window — though the chart itself always renders
  whatever `db_reader` fetched, not the narration-trimmed subset).
- **Liability**: category breakdown (horizontal bar), maturity profile
  (stacked bar — series = whichever liability categories the client
  actually has, not a hardcoded list; x-axis buckets ordered `<1Y, 1-3Y,
  3-5Y, >5Y`), rate exposure (bar, ordered `Fixed <5%, Fixed 5-7%, Fixed
  >7%, Floating`).
- Every chart degrades to a plain "No data available" placeholder instead
  of crashing when a client has no rows for that particular breakdown.

## 8. Data flow to the UI — session state

`app.py` is a single-file Streamlit script; state persists across reruns via
`st.session_state`. The relevant fields:

| Key | Set by | Meaning |
|---|---|---|
| `client_code`, `code_type` | sidebar submit / picker | the currently loaded `APR_CLIENT_CODE` |
| `client_summaries` | `load_client_dashboard()` | the full `generate_all_summaries()` result (summaries + `tab_data` + `rules` + `generated_at`) |
| `summaries_generated` | same | gate for whether the tab UI renders |
| `rm_code`, `rm_name`, `rm_clients` | RM-code sidebar submit | RM-search picker state — `resolve_lookup_code()`'s result |
| `chatbot` | lazily created | one `WholesaleBankingChatbot` instance per session, `update_client_code()`'d when the client changes |
| `messages` | chat turns | rendered chat history |

**Lookup flow**: submitting a code in the sidebar calls
`validate_client_code()` (`src/utils.py` — 6-7 chars → `RM_CODE`, 8-14 →
`APR_CLIENT_CODE`). An `APR_CLIENT_CODE` goes straight to
`load_client_dashboard()`. An `RM_CODE` calls
`db_reader.resolve_lookup_code()`, which populates `rm_clients` and renders
an HTML overview table (deliberately not `st.dataframe`, to avoid
Streamlit's pyarrow serialization path for a simple static table) plus a
sidebar selectbox; picking one and clicking **Load client dashboard** calls
the same `load_client_dashboard()` as a direct lookup would.

**Unknown-code handling**: `load_client_dashboard()` catches the
`ValueError` `db_reader` raises for a code that doesn't exist in
`CLIENT_MASTER` and shows `st.error(...)` — this is the UI-visible end of
the "never let an LLM see an unknown client" guarantee from §2 step 2.

## 9. Configuration reference

| Variable | Used by | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | `config/langchain_config.py` | all LLM calls (narration + chat + optional embeddings) |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | `config/db_config.py` | primary pooled connection (5 connections) |
| `DB_RO_USER`, `DB_RO_PASSWORD` | `config/db_config.py` | optional dedicated SELECT-only credentials for chat-generated SQL (3 connections); falls back to primary credentials if unset — the session is still forced read-only either way |
| `SUMMARY_CACHE_TTL_SECONDS` | `src/summary_cache.py` | dashboard cache lifetime, default 600 |

## 10. Guardrail summary (why an LLM can't do damage here)

1. **Tab path**: the LLM never sees a tool, never writes SQL, never picks
   what to query. The six views run unconditionally, every time, before any
   LLM call happens.
2. **Unknown client codes** raise before either pipeline reaches an LLM.
3. **Chat path's single tool** (`db_reader.execute_readonly_sql`) is only
   ever called with SQL that has passed `sql_guardrails.validate_sql()`:
   single `SELECT`, no DDL/DML anywhere in the AST, table allow-list from
   the retrieved schema slice, enforced `LIMIT`.
4. **Defense in depth at execution time**, independent of the validator:
   forced `READ ONLY` session, statement timeout, optional dedicated
   read-only DB role — so a validator bug still can't write or hang the DB.
5. **Narration is never a data source** in either pipeline — every prompt
   that produces user-facing prose is explicitly instructed to state only
   what's in the JSON it was handed, and both narrator prompts are
   temperature 0–0.1.
