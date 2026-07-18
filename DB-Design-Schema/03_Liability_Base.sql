-- =============================================================================
-- FILE:        03_Liability_Base.sql
-- TAB:         Liability Base
-- SCOPE:       Term deposits, current accounts, borrowings, and bonds, plus
--              maturity-profile, interest-rate, and value history tables that
--              feed the Liability Category / Maturity Profile / Interest Rate
--              Exposure charts already hardcoded in src/chart_generator.py.
-- OWNS:        LIABILITY_ACCOUNT_MASTER, LIABILITY_TERM_DEPOSIT_DETAILS,
--              LIABILITY_CURRENT_ACCOUNT_DETAILS, LIABILITY_BORROWING_DETAILS,
--              LIABILITY_BOND_DETAILS, LIABILITY_MATURITY_PROFILE,
--              LIABILITY_INTEREST_RATE_HISTORY, LIABILITY_VALUE_HISTORY,
--              LIABILITY_RISK_METRICS, LIABILITY_RENEWAL_HISTORY,
--              LIABILITY_EARLY_CLOSURE_HISTORY, LIABILITY_NOMINATION_DETAILS
-- REFERENCES:  CLIENT_MASTER, PRODUCT_MASTER, BRANCH_MASTER, CURRENCY_MASTER
--              (see 00_Master_Tables.sql) -- not redefined here.
--
-- DESIGN NOTE: LIABILITY_ACCOUNT_MASTER.LIABILITY_CATEGORY drives which
-- single detail table applies (table-per-subclass, mirrors 02_Asset_Base.sql):
-- 'Term Deposits' -> LIABILITY_TERM_DEPOSIT_DETAILS, 'Current Accounts' ->
-- LIABILITY_CURRENT_ACCOUNT_DETAILS, 'Borrowings' -> LIABILITY_BORROWING_DETAILS,
-- 'Bonds' -> LIABILITY_BOND_DETAILS. 'Other Liabilities' has no detail table
-- (header-only). These labels intentionally match src/chart_generator.py's
-- Liability Category Breakdown chart.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- LIABILITY_ACCOUNT_MASTER: header record for every liability-side account.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_ACCOUNT_MASTER (
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE       VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    PRODUCT_CODE          VARCHAR(10)  NOT NULL REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    LIABILITY_CATEGORY    VARCHAR(30)  NOT NULL,  -- Term Deposits / Current Accounts / Borrowings / Bonds / Other Liabilities
    BRANCH_CODE           VARCHAR(10)  REFERENCES BRANCH_MASTER(BRANCH_CODE),
    CURRENCY_CODE         VARCHAR(3)   REFERENCES CURRENCY_MASTER(CURRENCY_CODE),
    ACCOUNT_OPEN_DATE     DATE,
    MATURITY_DATE         DATE,
    ACCOUNT_STATUS        VARCHAR(20),  -- Active / Closed / Matured
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_LIABILITY_ACCOUNT_MASTER_CLIENT ON LIABILITY_ACCOUNT_MASTER (APR_CLIENT_CODE);
CREATE INDEX IX_LIABILITY_ACCOUNT_MASTER_CATEGORY ON LIABILITY_ACCOUNT_MASTER (LIABILITY_CATEGORY);


-- -----------------------------------------------------------------------------
-- LIABILITY_TERM_DEPOSIT_DETAILS: 1:1 detail for LIABILITY_CATEGORY = 'Term Deposits'.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_TERM_DEPOSIT_DETAILS (
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL PRIMARY KEY REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    DEPOSIT_AMOUNT        NUMERIC(18,2),
    INTEREST_RATE         NUMERIC(6,3),
    TENURE_MONTHS         INT,
    MATURITY_DATE         DATE,
    AUTO_RENEWAL_FLAG     CHAR(1)      DEFAULT 'N',
    PAYOUT_FREQUENCY      VARCHAR(20),  -- Monthly / Quarterly / Cumulative
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- LIABILITY_CURRENT_ACCOUNT_DETAILS: 1:1 detail for LIABILITY_CATEGORY = 'Current Accounts'.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_CURRENT_ACCOUNT_DETAILS (
    LIABILITY_ACCOUNT_ID      BIGINT       NOT NULL PRIMARY KEY REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    AVERAGE_MONTHLY_BALANCE   NUMERIC(18,2),
    MINIMUM_BALANCE_REQUIRED  NUMERIC(18,2),
    OVERDRAFT_LIMIT           NUMERIC(18,2),
    CREATED_DATE              TIMESTAMP    NOT NULL,
    UPDATED_DATE              TIMESTAMP,
    SOURCE_SYSTEM             VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- LIABILITY_BORROWING_DETAILS: 1:1 detail for LIABILITY_CATEGORY = 'Borrowings'.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_BORROWING_DETAILS (
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL PRIMARY KEY REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    BORROWING_TYPE        VARCHAR(30),  -- TermLoanTaken / CCBorrowing / Refinance
    LENDER_NAME           VARCHAR(150),
    PRINCIPAL_AMOUNT      NUMERIC(18,2),
    INTEREST_RATE         NUMERIC(6,3),
    REPAYMENT_TERMS       VARCHAR(300),
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- LIABILITY_BOND_DETAILS: 1:1 detail for LIABILITY_CATEGORY = 'Bonds' (bonds
-- issued by the bank / raised as liability funding, not client investments).
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_BOND_DETAILS (
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL PRIMARY KEY REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    BOND_TYPE             VARCHAR(30),
    ISIN_CODE             VARCHAR(12),
    ISSUE_DATE            DATE,
    FACE_VALUE            NUMERIC(18,2),
    COUPON_RATE           NUMERIC(6,3),
    MATURITY_DATE         DATE,
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- LIABILITY_MATURITY_PROFILE: pre-bucketed maturity amounts per account.
-- MATURITY_BUCKET values match src/chart_generator.py's Liability Maturity
-- Profile chart exactly. APR_CLIENT_CODE is denormalized for direct
-- client-level GROUP BY without joining through the account master.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_MATURITY_PROFILE (
    MATURITY_PROFILE_ID   BIGINT       NOT NULL PRIMARY KEY,
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    APR_CLIENT_CODE       VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    AS_OF_DATE            DATE         NOT NULL,
    MATURITY_BUCKET       VARCHAR(10)  NOT NULL,  -- <1Y / 1-3Y / 3-5Y / >5Y
    BUCKET_AMOUNT         NUMERIC(18,2) NOT NULL,
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_LIABILITY_MATURITY_PROFILE_CLIENT ON LIABILITY_MATURITY_PROFILE (APR_CLIENT_CODE, AS_OF_DATE);


-- -----------------------------------------------------------------------------
-- LIABILITY_INTEREST_RATE_HISTORY: rate change history per account.
-- RATE_BUCKET is pre-computed to match src/chart_generator.py's Interest Rate
-- Exposure chart buckets exactly, avoiding runtime bucketing logic in the
-- app or the LLM layer.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_INTEREST_RATE_HISTORY (
    RATE_HISTORY_ID        BIGINT       NOT NULL PRIMARY KEY,
    LIABILITY_ACCOUNT_ID   BIGINT       NOT NULL REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    APR_CLIENT_CODE        VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    EFFECTIVE_DATE         DATE         NOT NULL,
    INTEREST_RATE          NUMERIC(6,3) NOT NULL,
    RATE_TYPE              VARCHAR(10),  -- Fixed / Floating
    RATE_BUCKET            VARCHAR(20),  -- Fixed <5% / Fixed 5-7% / Fixed >7% / Floating
    CREATED_DATE           TIMESTAMP    NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);

CREATE INDEX IX_LIABILITY_INTEREST_RATE_HISTORY_CLIENT ON LIABILITY_INTEREST_RATE_HISTORY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- LIABILITY_VALUE_HISTORY: monthly total liability value per account, for
-- trend views (mirrors ASSET_VALUE_HISTORY in 02_Asset_Base.sql).
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_VALUE_HISTORY (
    VALUE_HISTORY_ID       BIGINT        NOT NULL PRIMARY KEY,
    LIABILITY_ACCOUNT_ID   BIGINT        NOT NULL REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    APR_CLIENT_CODE        VARCHAR(14)   NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    AS_OF_DATE             DATE          NOT NULL,
    LIABILITY_VALUE        NUMERIC(18,2) NOT NULL,
    CURRENCY_CODE          VARCHAR(3)    REFERENCES CURRENCY_MASTER(CURRENCY_CODE),
    CREATED_DATE           TIMESTAMP     NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);

CREATE INDEX IX_LIABILITY_VALUE_HISTORY_CLIENT_DATE ON LIABILITY_VALUE_HISTORY (APR_CLIENT_CODE, AS_OF_DATE);


-- -----------------------------------------------------------------------------
-- LIABILITY_RISK_METRICS: concentration/funding-stability risk indicators.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_RISK_METRICS (
    RISK_METRIC_ID                  BIGINT       NOT NULL PRIMARY KEY,
    LIABILITY_ACCOUNT_ID            BIGINT       NOT NULL REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    AS_OF_DATE                      DATE         NOT NULL,
    CONCENTRATION_RISK_PERCENTAGE   NUMERIC(5,2),
    FUNDING_STABILITY_RATING        VARCHAR(10),
    CREATED_DATE                    TIMESTAMP    NOT NULL,
    UPDATED_DATE                    TIMESTAMP,
    SOURCE_SYSTEM                   VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- LIABILITY_RENEWAL_HISTORY: term-deposit/borrowing renewal events.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_RENEWAL_HISTORY (
    RENEWAL_ID              BIGINT       NOT NULL PRIMARY KEY,
    LIABILITY_ACCOUNT_ID    BIGINT       NOT NULL REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    ORIGINAL_MATURITY_DATE  DATE,
    RENEWED_MATURITY_DATE   DATE,
    RENEWAL_DATE            DATE,
    RENEWED_AMOUNT          NUMERIC(18,2),
    CREATED_DATE            TIMESTAMP    NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- LIABILITY_EARLY_CLOSURE_HISTORY: premature closure events and penalties.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_EARLY_CLOSURE_HISTORY (
    CLOSURE_ID             BIGINT       NOT NULL PRIMARY KEY,
    LIABILITY_ACCOUNT_ID   BIGINT       NOT NULL REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    CLOSURE_DATE           DATE,
    CLOSURE_AMOUNT         NUMERIC(18,2),
    PENALTY_AMOUNT         NUMERIC(18,2),
    CLOSURE_REASON         VARCHAR(300),
    CREATED_DATE           TIMESTAMP    NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- LIABILITY_NOMINATION_DETAILS: nominee(s) registered against a liability
-- account (primarily relevant to deposit-type accounts).
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_NOMINATION_DETAILS (
    NOMINATION_ID          BIGINT       NOT NULL PRIMARY KEY,
    LIABILITY_ACCOUNT_ID   BIGINT       NOT NULL REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    NOMINEE_NAME           VARCHAR(150),
    RELATIONSHIP           VARCHAR(50),
    SHARE_PERCENTAGE       NUMERIC(5,2),
    CREATED_DATE           TIMESTAMP    NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);
