# DB-Design-Schema

Proposed SQL schema for driving the Wholesale Banking app's tabs from real
data instead of LLM-hallucinated content. This is a **design proposal**, not
a deployed schema — no application code in this repo connects to a database
yet (`app.py` currently generates every tab's content via free-form LLM
prompts, and `src/chart_generator.py`'s charts are hardcoded dummy data).

## Why this exists

Each tab in `app.py` needs to be backed by real, queryable tables so that:
1. The displayed numbers are **real data**, retrieved deterministically by SQL.
2. Business rules about *what* to show (thresholds, active/inactive, top-N,
   date windows) live in SQL/application code — not in an LLM prompt.
3. The LLM's only job becomes narrating the retrieved data into prose — never
   inventing figures.

## File index

| File | Tab | Tables | Purpose |
|---|---|---|---|
| `00_Master_Tables.sql` | *(shared)* | 8 | Client, RM, branch, currency, sector, product masters + account registry + RM-client mapping history |
| `01_CMS.sql` | CMS | 11 | Customer profile/address/contacts, communications, calls, meetings, documents, account balances (current + history), segment history, notes |
| `02_Asset_Base.sql` | Asset Base | 20 | Loans, trade finance, investments, securities, cash equivalents, collateral, NPA classification, sanction limits, covenants, guarantors, insurance, restructuring, write-offs |
| `03_Liability_Base.sql` | Liability Base | 12 | Term deposits, current accounts, borrowings, bonds, maturity profile, interest rate history, risk metrics, renewals, closures, nominations |
| `04_Product_Holdings.sql` | Product Holdings | 10 | Cross-product holding summary, utilization, cross-sell opportunities, fee income, relationship depth score, catalog features, pricing, channel usage, service requests |
| `05_RM_Details_Interactions.sql` | RM Details & Interactions | 7 | RM performance metrics, interaction rollups, visit plans, escalations, certifications, targets, client feedback |
| `06_RM_Discussion.sql` | RM Discussion | 6 | Discussion sessions, topics, needs identified, proposed solutions, follow-up actions, outcomes |

**Total: ~74 tables** across 7 files.

## Conventions

- **Naming**: `UPPER_SNAKE_CASE`, domain-prefixed (`CMS_`, `ASSET_`,
  `LIABILITY_`, `PRODUCT_`, `RM_`) — matches the one real field already in the
  codebase, `APR_CLIENT_CODE` (see `app.py`, `src/chatbot.py`).
- **SQL dialect**: portable ANSI SQL. No engine-specific syntax
  (`IDENTITY`/`SERIAL`/procedural blocks) — add the auto-increment mechanism
  for your chosen engine (SQL Server `IDENTITY`, Postgres `GENERATED ALWAYS AS
  IDENTITY`, Oracle `SEQUENCE` + trigger, etc.) at deployment time.
- **Keys**: surrogate PKs are `BIGINT PRIMARY KEY`; pure master tables use
  natural keys (`APR_CLIENT_CODE`, `RM_CODE`, `BRANCH_CODE`, etc).
- **Client scoping**: every transactional table carries `APR_CLIENT_CODE` and
  a leading index on it. This is deliberate — client-scoped queries (which is
  every query this app will ever run) stay sub-second even across 10-20 table
  joins, because the index lets the engine narrow to one client's rows before
  doing any join work. This is the single biggest performance lever discussed
  for this system; don't drop these indexes when deploying.
- **Audit columns**: every table ends with `CREATED_DATE`, `UPDATED_DATE`,
  `SOURCE_SYSTEM` for traceability back to whatever core-banking system feeds
  it.
- **No cross-tab duplication**: masters live only in `00_Master_Tables.sql`.
  Where two tabs conceptually overlap (e.g. CMS's raw call/meeting logs vs.
  RM Discussion's structured proposal/outcome content), the raw log stays in
  CMS and the other tab's table carries an `FK` back to it — see the header
  comment in `05_RM_Details_Interactions.sql` and `06_RM_Discussion.sql` for
  the specific cross-references.

## How the tabs relate

```
                    00_Master_Tables.sql
        (CLIENT_MASTER, RM_MASTER, PRODUCT_MASTER, ...)
                            |
      ---------------------------------------------------
      |          |            |             |            |
   01_CMS   02_Asset_Base  03_Liability   04_Product   05_RM_Details
      |                        _Base       _Holdings    _Interactions
      |                                                       |
      -----------------------> 06_RM_Discussion <-------------
         (MEETING_ID FK)          (RM_CODE, PRODUCT_CODE FK)
```

- `05_RM_Details_Interactions.sql` reads `01_CMS.sql`'s `CMS_CALL_LOG` /
  `CMS_MEETING_RECORD` / `CMS_COMMUNICATION_LOG` to build
  `RM_INTERACTION_SUMMARY` (a rollup, computed by an ETL/batch job — not a
  live 3-table join on every page load).
- `06_RM_Discussion.sql`'s `RM_DISCUSSION_SESSION` optionally links to
  `01_CMS.sql`'s `CMS_MEETING_RECORD` when a discussion was logged against a
  formal meeting.
- `02_Asset_Base.sql` and `03_Liability_Base.sql` both use a
  table-per-subclass pattern: one `..._ACCOUNT_MASTER` header table plus a
  1:1 detail table per category (e.g. `ASSET_LOAN_DETAILS`,
  `LIABILITY_TERM_DEPOSIT_DETAILS`), so a given account's category
  (`ASSET_CATEGORY` / `LIABILITY_CATEGORY`) determines which single detail
  table to join.
- Chart-shaped tables: `ASSET_VALUE_HISTORY`, `ASSET_QUALITY_HISTORY`,
  `LIABILITY_MATURITY_PROFILE`, and `LIABILITY_INTEREST_RATE_HISTORY` exist
  specifically so `src/chart_generator.py`'s existing chart categories
  (Asset Category Breakdown, Asset Quality Distribution, Asset Growth Trend,
  Liability Maturity Profile, Interest Rate Exposure) can be produced with a
  straight `GROUP BY` against real data, once that file is wired to the DB
  instead of its current hardcoded arrays.

## Not covered here (deliberately out of scope for this deliverable)

This folder is schema design only. Not included:
- Actual `CREATE VIEW` per tab (the deterministic "one query per tab" fetch
  layer discussed earlier) — a natural next step once a real engine is chosen.
- Sample/seed data.
- Engine-specific deployment scripts (sequences, partitioning, row-level
  security for multi-tenant access control).
- The NL2SQL / schema-RAG chatbot's metadata catalog (table/column
  descriptions for embedding) — would be generated *from* this schema once
  it's finalized.
