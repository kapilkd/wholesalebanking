# DB-Design-Schema/Views

The deterministic fetch layer described in `CLAUDE.md`'s "Target
architecture: the SQL flow" section:

```
CREATE VIEW per tab  →  Rules layer (app code)  →  LLM narration
```

These views are step one of that pipeline. They do all joining and
aggregation in SQL — no business-rule filtering (thresholds, top-N, date
windows) belongs here, that's the app-layer rules layer's job, applied
*after* querying a view. Views only do joins, aggregation, and
correctness-scoping (e.g. "the current RM mapping", "the latest balance
snapshot").

## How to query these views

Views take no parameters — that's engine-specific (T-SQL inline
table-valued functions, Postgres functions), and these are portable ANSI
SQL. Every view is queried the same way, with a `WHERE` filter:

```sql
SELECT * FROM VW_ASSET_BASE_SUMMARY WHERE APR_CLIENT_CODE = 'APR12345678';
```

This is why every base table in `DB-Design-Schema/*.sql` carries a leading
index on `APR_CLIENT_CODE` — the filter pushes down into indexed lookups on
every table the view joins, keeping even a 20-table join sub-second per the
execution-time estimate in `CLAUDE.md`.

`VW_RM_DISCUSSION_SUMMARY` is the one exception to "one row per client" (see
its file) — it returns one row per discussion session, so also add
`ORDER BY DISCUSSION_DATE DESC` when querying it; view row order is not
guaranteed by ANSI SQL without an explicit `ORDER BY` at query time.

## File index

| File | View(s) | Grain |
|---|---|---|
| `01_CMS_Views.sql` | `VW_CMS_SUMMARY` | 1 row / client |
| `02_Asset_Base_Views.sql` | `VW_ASSET_BASE_SUMMARY` | 1 row / client |
| | `VW_ASSET_CATEGORY_BREAKDOWN` | 1 row / client / category |
| | `VW_ASSET_QUALITY_DISTRIBUTION` | 1 row / client / NPA classification |
| | `VW_ASSET_GROWTH_TREND` | 1 row / client / month |
| `03_Liability_Base_Views.sql` | `VW_LIABILITY_BASE_SUMMARY` | 1 row / client |
| | `VW_LIABILITY_CATEGORY_BREAKDOWN` | 1 row / client / category |
| | `VW_LIABILITY_MATURITY_PROFILE` | 1 row / client / category / maturity bucket |
| | `VW_LIABILITY_RATE_EXPOSURE` | 1 row / client / rate bucket |
| `04_Product_Holdings_Views.sql` | `VW_PRODUCT_HOLDINGS_SUMMARY` | 1 row / client |
| `05_RM_Details_Interactions_Views.sql` | `VW_RM_DETAILS_SUMMARY` | 1 row / client |
| `06_RM_Discussion_Views.sql` | `VW_RM_DISCUSSION_SUMMARY` | 1 row / discussion session |

## Chart views → `src/chart_generator.py` mapping

Only Asset Base and Liability Base have chart views, because those are the
only two tabs `src/chart_generator.py` currently defines charts for.

| Chart view | Feeds this chart | Chart's hardcoded labels |
|---|---|---|
| `VW_ASSET_CATEGORY_BREAKDOWN` | "Asset Category Breakdown" (bar) | Corporate Loans, Trade Finance, Investments, Securities, Cash & Equivalents |
| `VW_ASSET_QUALITY_DISTRIBUTION` | "Asset Quality Distribution" (pie) | Standard, Sub-Standard, Doubtful, Loss |
| `VW_ASSET_GROWTH_TREND` | "Asset Growth Trend" (line) | monthly time series |
| `VW_LIABILITY_CATEGORY_BREAKDOWN` | "Liability Category Breakdown" (bar) | Term Deposits, Current Accounts, Borrowings, Bonds, Other Liabilities |
| `VW_LIABILITY_MATURITY_PROFILE` | "Liability Maturity Profile" (stacked bar) | <1Y/1-3Y/3-5Y/>5Y buckets — see label-mismatch note in `03_Liability_Base_Views.sql` |
| `VW_LIABILITY_RATE_EXPOSURE` | "Interest Rate Exposure" (bar) | Fixed <5%, Fixed 5-7%, Fixed >7%, Floating |

## Design principles (apply to any new view added here)

1. **No fan-out.** Never flatly `JOIN` a one-to-many child table (calls,
   meetings, disbursements, history rows) into a view meant to return one
   row per client/account — it silently multiplies every other joined
   column's values. Aggregate the child table first (a `WITH` CTE or derived
   table), then join the aggregate at the target grain.
2. **"Latest snapshot" pattern** for history tables: rank rows with
   `ROW_NUMBER() OVER (PARTITION BY <account_id> ORDER BY <date_col> DESC)`
   in a CTE and filter `WHERE RN = 1`, rather than a correlated `MAX()`
   subquery per row.
3. **Portability**: `WITH` CTEs (SQL:1999) and window functions (SQL:2003)
   are used throughout — supported by SQL Server 2012+, PostgreSQL, Oracle,
   and MySQL 8+. `VW_ASSET_GROWTH_TREND` additionally uses
   `EXTRACT(YEAR/MONTH FROM date)`, native on SQL Server only from the 2022
   release onward (earlier versions: substitute `DATEPART`).
4. Chart views intentionally return multiple rows per client (one per
   category/bucket/month) — that's correct, they feed a charting library's
   `x`/`y` arrays directly.

## Not covered here

- Materialization/indexing strategy for these views (e.g. materialized
  views, indexed views) — a performance decision for deployment time, not
  schema design time.
- Row-level security / multi-tenant access control on the views.
- The rules layer itself (thresholds, top-N, date windows) — lives in
  application code, not SQL, per `CLAUDE.md`.
