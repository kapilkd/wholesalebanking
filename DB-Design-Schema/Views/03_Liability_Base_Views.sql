-- =============================================================================
-- FILE:        Views/03_Liability_Base_Views.sql
-- TAB:         Liability Base
-- SOURCE TABLES: ../03_Liability_Base.sql, ../00_Master_Tables.sql
-- SCOPE:       One summary view (1 row/client) + three chart views, one per
--              chart in src/chart_generator.py's generate_liability_charts().
-- OWNS:        VW_LIABILITY_BASE_SUMMARY, VW_LIABILITY_CATEGORY_BREAKDOWN,
--              VW_LIABILITY_MATURITY_PROFILE, VW_LIABILITY_RATE_EXPOSURE
--
-- USAGE: views take no parameters; the app queries with a WHERE filter, e.g.:
--     SELECT * FROM VW_LIABILITY_BASE_SUMMARY WHERE APR_CLIENT_CODE = ?
--
-- PORTABILITY NOTE: see ../02_Asset_Base.sql's Views file header -- same
-- window function / CTE portability applies here (no EXTRACT() used in this
-- file, since Liability has no growth-trend chart, only category/maturity/
-- rate charts).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- VW_LIABILITY_BASE_SUMMARY: 1 row per client. Mirrors VW_ASSET_BASE_SUMMARY's
-- approach: latest snapshot per account, aggregated to client grain.
-- -----------------------------------------------------------------------------
CREATE VIEW VW_LIABILITY_BASE_SUMMARY AS
WITH LATEST_VALUE AS (
    SELECT LIABILITY_ACCOUNT_ID, LIABILITY_VALUE
    FROM (
        SELECT LIABILITY_ACCOUNT_ID, LIABILITY_VALUE,
               ROW_NUMBER() OVER (PARTITION BY LIABILITY_ACCOUNT_ID ORDER BY AS_OF_DATE DESC) AS RN
        FROM LIABILITY_VALUE_HISTORY
    ) R
    WHERE R.RN = 1
),
LATEST_RATE AS (
    SELECT LIABILITY_ACCOUNT_ID, INTEREST_RATE
    FROM (
        SELECT LIABILITY_ACCOUNT_ID, INTEREST_RATE,
               ROW_NUMBER() OVER (PARTITION BY LIABILITY_ACCOUNT_ID ORDER BY EFFECTIVE_DATE DESC) AS RN
        FROM LIABILITY_INTEREST_RATE_HISTORY
    ) R
    WHERE R.RN = 1
),
LATEST_RISK AS (
    SELECT LIABILITY_ACCOUNT_ID, CONCENTRATION_RISK_PERCENTAGE
    FROM (
        SELECT LIABILITY_ACCOUNT_ID, CONCENTRATION_RISK_PERCENTAGE,
               ROW_NUMBER() OVER (PARTITION BY LIABILITY_ACCOUNT_ID ORDER BY AS_OF_DATE DESC) AS RN
        FROM LIABILITY_RISK_METRICS
    ) R
    WHERE R.RN = 1
),
ACCOUNT_ROLLUP AS (
    SELECT
        LAM.APR_CLIENT_CODE,
        COUNT(*) AS TOTAL_LIABILITY_ACCOUNTS,
        SUM(LV.LIABILITY_VALUE) AS TOTAL_LIABILITY_VALUE,
        AVG(LR.INTEREST_RATE) AS AVERAGE_INTEREST_RATE,
        AVG(RISK.CONCENTRATION_RISK_PERCENTAGE) AS AVERAGE_CONCENTRATION_RISK_PERCENTAGE
    FROM LIABILITY_ACCOUNT_MASTER LAM
    LEFT JOIN LATEST_VALUE LV ON LV.LIABILITY_ACCOUNT_ID = LAM.LIABILITY_ACCOUNT_ID
    LEFT JOIN LATEST_RATE LR ON LR.LIABILITY_ACCOUNT_ID = LAM.LIABILITY_ACCOUNT_ID
    LEFT JOIN LATEST_RISK RISK ON RISK.LIABILITY_ACCOUNT_ID = LAM.LIABILITY_ACCOUNT_ID
    GROUP BY LAM.APR_CLIENT_CODE
)
SELECT
    C.APR_CLIENT_CODE,
    COALESCE(AR.TOTAL_LIABILITY_ACCOUNTS, 0) AS TOTAL_LIABILITY_ACCOUNTS,
    COALESCE(AR.TOTAL_LIABILITY_VALUE, 0)    AS TOTAL_LIABILITY_VALUE,
    AR.AVERAGE_INTEREST_RATE,
    AR.AVERAGE_CONCENTRATION_RISK_PERCENTAGE
FROM CLIENT_MASTER C
LEFT JOIN ACCOUNT_ROLLUP AR ON AR.APR_CLIENT_CODE = C.APR_CLIENT_CODE;


-- -----------------------------------------------------------------------------
-- VW_LIABILITY_CATEGORY_BREAKDOWN: 1 row per client+category. Feeds chart
-- "Liability Category Breakdown" -- LIABILITY_CATEGORY values (Term Deposits
-- / Current Accounts / Borrowings / Bonds / Other Liabilities) match the
-- chart's hardcoded labels exactly (see ../03_Liability_Base.sql design note).
-- -----------------------------------------------------------------------------
CREATE VIEW VW_LIABILITY_CATEGORY_BREAKDOWN AS
WITH LATEST_VALUE AS (
    SELECT LIABILITY_ACCOUNT_ID, LIABILITY_VALUE
    FROM (
        SELECT LIABILITY_ACCOUNT_ID, LIABILITY_VALUE,
               ROW_NUMBER() OVER (PARTITION BY LIABILITY_ACCOUNT_ID ORDER BY AS_OF_DATE DESC) AS RN
        FROM LIABILITY_VALUE_HISTORY
    ) R
    WHERE R.RN = 1
)
SELECT
    LAM.APR_CLIENT_CODE,
    LAM.LIABILITY_CATEGORY,
    SUM(LV.LIABILITY_VALUE) AS CATEGORY_VALUE
FROM LIABILITY_ACCOUNT_MASTER LAM
JOIN LATEST_VALUE LV ON LV.LIABILITY_ACCOUNT_ID = LAM.LIABILITY_ACCOUNT_ID
GROUP BY LAM.APR_CLIENT_CODE, LAM.LIABILITY_CATEGORY;


-- -----------------------------------------------------------------------------
-- VW_LIABILITY_MATURITY_PROFILE: 1 row per client+category+bucket. Feeds
-- chart "Liability Maturity Profile". Thin aggregation over
-- LIABILITY_MATURITY_PROFILE, which is already pre-bucketed at table-design
-- time -- this view just takes the latest AS_OF_DATE snapshot per account
-- and sums by category+bucket.
--
-- NOTE FOR THE APP LAYER (not silently handled here): the table's bucket
-- labels ('<1Y'/'1-3Y'/'3-5Y'/'>5Y') and the chart's hardcoded labels
-- ('< 1 Year'/'1-3 Years'/'3-5 Years'/'> 5 Years') are the same buckets with
-- different string literals -- map them when wiring chart_generator.py. Also,
-- the chart currently only plots 3 of these 5 liability categories (Term
-- Deposits/Borrowings/Bonds, as "Deposits"/"Borrowings"/"Bonds") -- this view
-- returns all 5 categories faithfully; narrow to the chart's 3 series in the
-- app layer, not here.
-- -----------------------------------------------------------------------------
CREATE VIEW VW_LIABILITY_MATURITY_PROFILE AS
WITH LATEST_MATURITY AS (
    SELECT LIABILITY_ACCOUNT_ID, APR_CLIENT_CODE, MATURITY_BUCKET, BUCKET_AMOUNT
    FROM (
        SELECT LIABILITY_ACCOUNT_ID, APR_CLIENT_CODE, MATURITY_BUCKET, BUCKET_AMOUNT,
               ROW_NUMBER() OVER (PARTITION BY LIABILITY_ACCOUNT_ID ORDER BY AS_OF_DATE DESC) AS RN
        FROM LIABILITY_MATURITY_PROFILE
    ) R
    WHERE R.RN = 1
)
SELECT
    LM.APR_CLIENT_CODE,
    LAM.LIABILITY_CATEGORY,
    LM.MATURITY_BUCKET,
    SUM(LM.BUCKET_AMOUNT) AS BUCKET_TOTAL
FROM LATEST_MATURITY LM
JOIN LIABILITY_ACCOUNT_MASTER LAM ON LAM.LIABILITY_ACCOUNT_ID = LM.LIABILITY_ACCOUNT_ID
GROUP BY LM.APR_CLIENT_CODE, LAM.LIABILITY_CATEGORY, LM.MATURITY_BUCKET;


-- -----------------------------------------------------------------------------
-- VW_LIABILITY_RATE_EXPOSURE: 1 row per client+rate bucket. Feeds chart
-- "Interest Rate Exposure" -- RATE_BUCKET values are already pre-computed at
-- table-design time to match the chart's 'Fixed <5%'/'Fixed 5-7%'/
-- 'Fixed >7%'/'Floating' labels. BUCKET_VALUE is the liability amount
-- exposed at that rate bucket (a more directly useful banking metric than a
-- raw count); convert to a percentage of total in the app layer if the chart
-- needs it in that form.
-- -----------------------------------------------------------------------------
CREATE VIEW VW_LIABILITY_RATE_EXPOSURE AS
WITH LATEST_RATE AS (
    SELECT LIABILITY_ACCOUNT_ID, APR_CLIENT_CODE, RATE_BUCKET
    FROM (
        SELECT LIABILITY_ACCOUNT_ID, APR_CLIENT_CODE, RATE_BUCKET,
               ROW_NUMBER() OVER (PARTITION BY LIABILITY_ACCOUNT_ID ORDER BY EFFECTIVE_DATE DESC) AS RN
        FROM LIABILITY_INTEREST_RATE_HISTORY
    ) R
    WHERE R.RN = 1
),
LATEST_VALUE AS (
    SELECT LIABILITY_ACCOUNT_ID, LIABILITY_VALUE
    FROM (
        SELECT LIABILITY_ACCOUNT_ID, LIABILITY_VALUE,
               ROW_NUMBER() OVER (PARTITION BY LIABILITY_ACCOUNT_ID ORDER BY AS_OF_DATE DESC) AS RN
        FROM LIABILITY_VALUE_HISTORY
    ) R
    WHERE R.RN = 1
)
SELECT
    LR.APR_CLIENT_CODE,
    LR.RATE_BUCKET,
    COALESCE(SUM(LV.LIABILITY_VALUE), 0) AS BUCKET_VALUE
FROM LATEST_RATE LR
LEFT JOIN LATEST_VALUE LV ON LV.LIABILITY_ACCOUNT_ID = LR.LIABILITY_ACCOUNT_ID
GROUP BY LR.APR_CLIENT_CODE, LR.RATE_BUCKET;
