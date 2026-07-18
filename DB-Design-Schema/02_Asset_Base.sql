-- =============================================================================
-- FILE:        02_Asset_Base.sql
-- TAB:         Asset Base
-- SCOPE:       Everything the "Asset Base" tab needs: loans, trade finance,
--              investments, securities, cash equivalents, plus collateral,
--              NPA classification, and history tables that feed the
--              Asset Category / Asset Quality / Asset Growth charts already
--              hardcoded in src/chart_generator.py.
-- OWNS:        ASSET_ACCOUNT_MASTER, ASSET_LOAN_DETAILS,
--              ASSET_LOAN_DISBURSEMENT_SCHEDULE, ASSET_LOAN_REPAYMENT_SCHEDULE,
--              ASSET_TRADE_FINANCE_DETAILS, ASSET_INVESTMENT_DETAILS,
--              ASSET_SECURITIES_DETAILS, ASSET_CASH_EQUIVALENT_DETAILS,
--              ASSET_COLLATERAL_MASTER, ASSET_COLLATERAL_LINKAGE,
--              ASSET_NPA_CLASSIFICATION, ASSET_QUALITY_HISTORY,
--              ASSET_VALUE_HISTORY, ASSET_INTEREST_RATE_HISTORY,
--              ASSET_SANCTION_LIMIT, ASSET_COVENANT_MASTER,
--              ASSET_GUARANTOR_DETAILS, ASSET_INSURANCE_DETAILS,
--              ASSET_RESTRUCTURING_HISTORY, ASSET_WRITEOFF_RECOVERY  (20 tables)
-- REFERENCES:  CLIENT_MASTER, PRODUCT_MASTER, BRANCH_MASTER, CURRENCY_MASTER
--              (see 00_Master_Tables.sql) -- not redefined here.
--
-- DESIGN NOTE: ASSET_ACCOUNT_MASTER.ASSET_CATEGORY drives which single detail
-- table applies to a given asset account (1:1 sub-type tables, similar to
-- table-per-subclass): 'Corporate Loans' -> ASSET_LOAN_DETAILS,
-- 'Trade Finance' -> ASSET_TRADE_FINANCE_DETAILS, 'Investments' ->
-- ASSET_INVESTMENT_DETAILS, 'Securities' -> ASSET_SECURITIES_DETAILS,
-- 'Cash & Equivalents' -> ASSET_CASH_EQUIVALENT_DETAILS. These category
-- labels intentionally match src/chart_generator.py's Asset Category chart.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- ASSET_ACCOUNT_MASTER: header record for every asset-side account/facility.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_ACCOUNT_MASTER (
    ASSET_ACCOUNT_ID  BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    PRODUCT_CODE      VARCHAR(10)  NOT NULL REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    ASSET_CATEGORY    VARCHAR(30)  NOT NULL,  -- Corporate Loans / Trade Finance / Investments / Securities / Cash & Equivalents
    BRANCH_CODE       VARCHAR(10)  REFERENCES BRANCH_MASTER(BRANCH_CODE),
    CURRENCY_CODE     VARCHAR(3)   REFERENCES CURRENCY_MASTER(CURRENCY_CODE),
    SANCTION_DATE     DATE,
    MATURITY_DATE     DATE,
    ACCOUNT_STATUS    VARCHAR(20),  -- Active / Closed / Written-Off
    CREATED_DATE      TIMESTAMP    NOT NULL,
    UPDATED_DATE      TIMESTAMP,
    SOURCE_SYSTEM     VARCHAR(30)
);

CREATE INDEX IX_ASSET_ACCOUNT_MASTER_CLIENT ON ASSET_ACCOUNT_MASTER (APR_CLIENT_CODE);
CREATE INDEX IX_ASSET_ACCOUNT_MASTER_CATEGORY ON ASSET_ACCOUNT_MASTER (ASSET_CATEGORY);


-- -----------------------------------------------------------------------------
-- ASSET_LOAN_DETAILS: 1:1 detail for ASSET_CATEGORY = 'Corporate Loans'.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_LOAN_DETAILS (
    ASSET_ACCOUNT_ID       BIGINT       NOT NULL PRIMARY KEY REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    LOAN_TYPE               VARCHAR(30),  -- Term Loan / Working Capital / Overdraft / Cash Credit
    SANCTIONED_AMOUNT       NUMERIC(18,2),
    DISBURSED_AMOUNT        NUMERIC(18,2),
    OUTSTANDING_AMOUNT      NUMERIC(18,2),
    INTEREST_RATE           NUMERIC(6,3),
    REPAYMENT_FREQUENCY     VARCHAR(20),
    TENURE_MONTHS           INT,
    CREATED_DATE            TIMESTAMP    NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- ASSET_LOAN_DISBURSEMENT_SCHEDULE: tranche-wise disbursement history.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_LOAN_DISBURSEMENT_SCHEDULE (
    DISBURSEMENT_ID       BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID      BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    TRANCHE_NUMBER        INT,
    DISBURSEMENT_DATE     DATE,
    DISBURSEMENT_AMOUNT   NUMERIC(18,2),
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_ASSET_LOAN_DISB_SCHED_ACCT ON ASSET_LOAN_DISBURSEMENT_SCHEDULE (ASSET_ACCOUNT_ID);


-- -----------------------------------------------------------------------------
-- ASSET_LOAN_REPAYMENT_SCHEDULE: installment-wise repayment schedule.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_LOAN_REPAYMENT_SCHEDULE (
    REPAYMENT_ID          BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID      BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    INSTALLMENT_NUMBER    INT,
    DUE_DATE              DATE         NOT NULL,
    PRINCIPAL_DUE         NUMERIC(18,2),
    INTEREST_DUE          NUMERIC(18,2),
    PAYMENT_STATUS        VARCHAR(20),  -- Paid / Overdue / Pending
    PAID_DATE             DATE,
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_ASSET_LOAN_REPAY_SCHED_ACCT ON ASSET_LOAN_REPAYMENT_SCHEDULE (ASSET_ACCOUNT_ID);


-- -----------------------------------------------------------------------------
-- ASSET_TRADE_FINANCE_DETAILS: 1:1 detail for ASSET_CATEGORY = 'Trade Finance'.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_TRADE_FINANCE_DETAILS (
    ASSET_ACCOUNT_ID        BIGINT       NOT NULL PRIMARY KEY REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    TRADE_INSTRUMENT_TYPE   VARCHAR(30),  -- LC / BG / BillDiscounting / ExportFinance
    INSTRUMENT_NUMBER       VARCHAR(30),
    ISSUE_DATE              DATE,
    EXPIRY_DATE             DATE,
    BENEFICIARY_NAME        VARCHAR(200),
    EXPOSURE_AMOUNT         NUMERIC(18,2),
    CREATED_DATE            TIMESTAMP    NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- ASSET_INVESTMENT_DETAILS: 1:1 detail for ASSET_CATEGORY = 'Investments'.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_INVESTMENT_DETAILS (
    ASSET_ACCOUNT_ID       BIGINT        NOT NULL PRIMARY KEY REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    INVESTMENT_TYPE        VARCHAR(30),  -- Bonds / MutualFund / Equity / AIF
    INSTRUMENT_NAME        VARCHAR(150),
    ISIN_CODE              VARCHAR(12),
    UNITS_HELD             NUMERIC(18,4),
    PURCHASE_PRICE         NUMERIC(18,4),
    CURRENT_MARKET_VALUE   NUMERIC(18,2),
    PURCHASE_DATE          DATE,
    CREATED_DATE           TIMESTAMP     NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- ASSET_SECURITIES_DETAILS: 1:1 detail for ASSET_CATEGORY = 'Securities'.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_SECURITIES_DETAILS (
    ASSET_ACCOUNT_ID   BIGINT        NOT NULL PRIMARY KEY REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    SECURITY_TYPE      VARCHAR(30),  -- G-Sec / CorporateBond / Debenture / CP
    FACE_VALUE         NUMERIC(18,2),
    COUPON_RATE        NUMERIC(6,3),
    MATURITY_DATE      DATE,
    CREDIT_RATING      VARCHAR(10),
    RATING_AGENCY      VARCHAR(50),
    CREATED_DATE       TIMESTAMP     NOT NULL,
    UPDATED_DATE       TIMESTAMP,
    SOURCE_SYSTEM      VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- ASSET_CASH_EQUIVALENT_DETAILS: 1:1 detail for ASSET_CATEGORY = 'Cash & Equivalents'.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_CASH_EQUIVALENT_DETAILS (
    ASSET_ACCOUNT_ID   BIGINT        NOT NULL PRIMARY KEY REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    INSTRUMENT_TYPE    VARCHAR(30),  -- FixedDeposit / CertificateOfDeposit / CommercialPaper
    PRINCIPAL_AMOUNT   NUMERIC(18,2),
    INTEREST_RATE      NUMERIC(6,3),
    DEPOSIT_DATE       DATE,
    MATURITY_DATE      DATE,
    CREATED_DATE       TIMESTAMP     NOT NULL,
    UPDATED_DATE       TIMESTAMP,
    SOURCE_SYSTEM      VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- ASSET_COLLATERAL_MASTER: collateral pledged by the client (may secure
-- multiple asset accounts, see ASSET_COLLATERAL_LINKAGE below).
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_COLLATERAL_MASTER (
    COLLATERAL_ID          BIGINT        NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE        VARCHAR(14)   NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    COLLATERAL_TYPE        VARCHAR(30),  -- Property / Stock / Receivables / Guarantee / FixedAsset
    COLLATERAL_DESCRIPTION VARCHAR(300),
    COLLATERAL_VALUE       NUMERIC(18,2),
    VALUATION_DATE         DATE,
    VALUATION_AGENCY       VARCHAR(100),
    CREATED_DATE           TIMESTAMP     NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);

CREATE INDEX IX_ASSET_COLLATERAL_MASTER_CLIENT ON ASSET_COLLATERAL_MASTER (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- ASSET_COLLATERAL_LINKAGE: many-to-many link between collateral and the
-- asset accounts it secures.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_COLLATERAL_LINKAGE (
    LINKAGE_ID            BIGINT       NOT NULL PRIMARY KEY,
    COLLATERAL_ID         BIGINT       NOT NULL REFERENCES ASSET_COLLATERAL_MASTER(COLLATERAL_ID),
    ASSET_ACCOUNT_ID      BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    COVERAGE_PERCENTAGE   NUMERIC(5,2),
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_ASSET_COLLATERAL_LINKAGE_ACCT ON ASSET_COLLATERAL_LINKAGE (ASSET_ACCOUNT_ID);


-- -----------------------------------------------------------------------------
-- ASSET_NPA_CLASSIFICATION: current NPA/asset-quality classification per
-- account. Values match src/chart_generator.py's Asset Quality Distribution
-- chart exactly.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_NPA_CLASSIFICATION (
    NPA_ID                  BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID        BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    CLASSIFICATION_DATE     DATE         NOT NULL,
    ASSET_CLASSIFICATION    VARCHAR(20)  NOT NULL,  -- Standard / Sub-Standard / Doubtful / Loss
    DPD_DAYS                INT,                    -- days past due
    PROVISION_AMOUNT        NUMERIC(18,2),
    PROVISION_PERCENTAGE    NUMERIC(5,2),
    CREATED_DATE            TIMESTAMP    NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);

CREATE INDEX IX_ASSET_NPA_CLASSIFICATION_ACCT ON ASSET_NPA_CLASSIFICATION (ASSET_ACCOUNT_ID);


-- -----------------------------------------------------------------------------
-- ASSET_QUALITY_HISTORY: monthly snapshot of classification + outstanding
-- amount per account, for the Asset Quality trend view.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_QUALITY_HISTORY (
    QUALITY_HISTORY_ID     BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID       BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    AS_OF_DATE              DATE        NOT NULL,
    ASSET_CLASSIFICATION    VARCHAR(20),
    OUTSTANDING_AMOUNT      NUMERIC(18,2),
    CREATED_DATE            TIMESTAMP   NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);

CREATE INDEX IX_ASSET_QUALITY_HISTORY_ACCT_DATE ON ASSET_QUALITY_HISTORY (ASSET_ACCOUNT_ID, AS_OF_DATE);


-- -----------------------------------------------------------------------------
-- ASSET_VALUE_HISTORY: monthly total asset value per account. APR_CLIENT_CODE
-- is denormalized so the client-level "Asset Growth Trend" chart in
-- src/chart_generator.py can aggregate with a single GROUP BY, no joins.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_VALUE_HISTORY (
    VALUE_HISTORY_ID    BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID    BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    APR_CLIENT_CODE     VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    AS_OF_DATE          DATE         NOT NULL,
    ASSET_VALUE         NUMERIC(18,2) NOT NULL,
    CURRENCY_CODE       VARCHAR(3)   REFERENCES CURRENCY_MASTER(CURRENCY_CODE),
    CREATED_DATE        TIMESTAMP    NOT NULL,
    UPDATED_DATE        TIMESTAMP,
    SOURCE_SYSTEM       VARCHAR(30)
);

CREATE INDEX IX_ASSET_VALUE_HISTORY_CLIENT_DATE ON ASSET_VALUE_HISTORY (APR_CLIENT_CODE, AS_OF_DATE);


-- -----------------------------------------------------------------------------
-- ASSET_INTEREST_RATE_HISTORY: rate change history per account.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_INTEREST_RATE_HISTORY (
    RATE_HISTORY_ID    BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID   BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    EFFECTIVE_DATE     DATE         NOT NULL,
    INTEREST_RATE      NUMERIC(6,3) NOT NULL,
    RATE_TYPE          VARCHAR(10),  -- Fixed / Floating
    BENCHMARK_NAME     VARCHAR(20),  -- MCLR / REPO / T-Bill / EBLR
    CREATED_DATE       TIMESTAMP    NOT NULL,
    UPDATED_DATE       TIMESTAMP,
    SOURCE_SYSTEM      VARCHAR(30)
);

CREATE INDEX IX_ASSET_INTEREST_RATE_HISTORY_ACCT ON ASSET_INTEREST_RATE_HISTORY (ASSET_ACCOUNT_ID);


-- -----------------------------------------------------------------------------
-- ASSET_SANCTION_LIMIT: client/product-level sanctioned credit limits and
-- current utilization (may span several ASSET_ACCOUNT_MASTER rows).
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_SANCTION_LIMIT (
    SANCTION_LIMIT_ID       BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE         VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    PRODUCT_CODE            VARCHAR(10)  REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    SANCTIONED_LIMIT_AMOUNT NUMERIC(18,2),
    UTILIZED_LIMIT_AMOUNT   NUMERIC(18,2),
    AVAILABLE_LIMIT_AMOUNT  NUMERIC(18,2),
    LIMIT_REVIEW_DATE       DATE,
    LIMIT_EXPIRY_DATE       DATE,
    CREATED_DATE            TIMESTAMP    NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);

CREATE INDEX IX_ASSET_SANCTION_LIMIT_CLIENT ON ASSET_SANCTION_LIMIT (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- ASSET_COVENANT_MASTER: loan covenants and their compliance status.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_COVENANT_MASTER (
    COVENANT_ID            BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID       BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    COVENANT_TYPE          VARCHAR(50),
    COVENANT_DESCRIPTION   VARCHAR(500),
    COMPLIANCE_STATUS      VARCHAR(20),  -- Compliant / Breach / UnderReview
    REVIEW_DATE            DATE,
    CREATED_DATE           TIMESTAMP    NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);

CREATE INDEX IX_ASSET_COVENANT_MASTER_ACCT ON ASSET_COVENANT_MASTER (ASSET_ACCOUNT_ID);


-- -----------------------------------------------------------------------------
-- ASSET_GUARANTOR_DETAILS: guarantors backing an asset account.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_GUARANTOR_DETAILS (
    GUARANTOR_ID       BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID   BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    GUARANTOR_NAME     VARCHAR(200),
    GUARANTOR_TYPE     VARCHAR(20),  -- Individual / Corporate
    GUARANTEE_AMOUNT   NUMERIC(18,2),
    CREATED_DATE       TIMESTAMP    NOT NULL,
    UPDATED_DATE       TIMESTAMP,
    SOURCE_SYSTEM      VARCHAR(30)
);

CREATE INDEX IX_ASSET_GUARANTOR_DETAILS_ACCT ON ASSET_GUARANTOR_DETAILS (ASSET_ACCOUNT_ID);


-- -----------------------------------------------------------------------------
-- ASSET_INSURANCE_DETAILS: insurance policies covering collateral/assets.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_INSURANCE_DETAILS (
    INSURANCE_ID        BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID    BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    POLICY_NUMBER       VARCHAR(30),
    INSURER_NAME        VARCHAR(150),
    SUM_INSURED_AMOUNT  NUMERIC(18,2),
    POLICY_START_DATE   DATE,
    POLICY_END_DATE     DATE,
    CREATED_DATE        TIMESTAMP    NOT NULL,
    UPDATED_DATE        TIMESTAMP,
    SOURCE_SYSTEM       VARCHAR(30)
);

CREATE INDEX IX_ASSET_INSURANCE_DETAILS_ACCT ON ASSET_INSURANCE_DETAILS (ASSET_ACCOUNT_ID);


-- -----------------------------------------------------------------------------
-- ASSET_RESTRUCTURING_HISTORY: loan restructuring events and term changes.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_RESTRUCTURING_HISTORY (
    RESTRUCTURE_ID       BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID     BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    RESTRUCTURE_DATE     DATE         NOT NULL,
    RESTRUCTURE_REASON   VARCHAR(300),
    OLD_TERMS            VARCHAR(500),
    NEW_TERMS            VARCHAR(500),
    CREATED_DATE         TIMESTAMP    NOT NULL,
    UPDATED_DATE         TIMESTAMP,
    SOURCE_SYSTEM        VARCHAR(30)
);

CREATE INDEX IX_ASSET_RESTRUCTURING_HISTORY_ACCT ON ASSET_RESTRUCTURING_HISTORY (ASSET_ACCOUNT_ID);


-- -----------------------------------------------------------------------------
-- ASSET_WRITEOFF_RECOVERY: write-off and subsequent recovery events.
-- -----------------------------------------------------------------------------
CREATE TABLE ASSET_WRITEOFF_RECOVERY (
    WRITEOFF_ID       BIGINT       NOT NULL PRIMARY KEY,
    ASSET_ACCOUNT_ID  BIGINT       NOT NULL REFERENCES ASSET_ACCOUNT_MASTER(ASSET_ACCOUNT_ID),
    WRITEOFF_DATE     DATE,
    WRITEOFF_AMOUNT   NUMERIC(18,2),
    RECOVERY_DATE     DATE,
    RECOVERY_AMOUNT   NUMERIC(18,2),
    CREATED_DATE      TIMESTAMP    NOT NULL,
    UPDATED_DATE      TIMESTAMP,
    SOURCE_SYSTEM     VARCHAR(30)
);

CREATE INDEX IX_ASSET_WRITEOFF_RECOVERY_ACCT ON ASSET_WRITEOFF_RECOVERY (ASSET_ACCOUNT_ID);
