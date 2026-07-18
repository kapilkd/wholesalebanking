-- =============================================================================
-- MariaDB/MySQL deployment copy, generated from ../03_Liability_Base.sql for the local
-- XAMPP MariaDB instance (wholesale DB, 127.0.0.1:3306). Adaptations from
-- the portable ANSI SQL design source:
--   1. AUTO_INCREMENT added to surrogate BIGINT primary keys (omitted in the
--      design source as engine-specific; this IS that deployment step).
--   2. ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 added to every CREATE TABLE.
--   3. CREATED_DATE/UPDATED_DATE given explicit DEFAULT CURRENT_TIMESTAMP /
--      NULL DEFAULT NULL (MariaDB strict mode rejects the implicit default
--      on a second TIMESTAMP column otherwise).
--   4. Inline column-level REFERENCES converted to explicit table-level
--      CONSTRAINT ... FOREIGN KEY clauses. MySQL/MariaDB PARSES inline
--      REFERENCES but does NOT enforce it as a real constraint -- this is a
--      documented MySQL quirk, confirmed here by SHOW CREATE TABLE / KEY_
--      COLUMN_USAGE showing zero FKs after the first deploy attempt.
-- The design source (../03_Liability_Base.sql) remains the source of truth for schema
-- design; this file is a build artifact of it, not hand-maintained.
-- =============================================================================

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
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE       VARCHAR(14)  NOT NULL,
    PRODUCT_CODE          VARCHAR(10)  NOT NULL,
    LIABILITY_CATEGORY    VARCHAR(30)  NOT NULL,  -- Term Deposits / Current Accounts / Borrowings / Bonds / Other Liabilities
    BRANCH_CODE           VARCHAR(10),
    CURRENCY_CODE         VARCHAR(3),
    ACCOUNT_OPEN_DATE     DATE,
    MATURITY_DATE         DATE,
    ACCOUNT_STATUS        VARCHAR(20),  -- Active / Closed / Matured
    CREATED_DATE          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE          TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM         VARCHAR(30),
    CONSTRAINT FK_LIABILITY_ACCOUNT_MASTER_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_LIABILITY_ACCOUNT_MASTER_PRODUCT_CODE FOREIGN KEY (PRODUCT_CODE) REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    CONSTRAINT FK_LIABILITY_ACCOUNT_MASTER_BRANCH_CODE FOREIGN KEY (BRANCH_CODE) REFERENCES BRANCH_MASTER(BRANCH_CODE),
    CONSTRAINT FK_LIABILITY_ACCOUNT_MASTER_CURRENCY_CODE FOREIGN KEY (CURRENCY_CODE) REFERENCES CURRENCY_MASTER(CURRENCY_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_LIABILITY_ACCOUNT_MASTER_CLIENT ON LIABILITY_ACCOUNT_MASTER (APR_CLIENT_CODE);
CREATE INDEX IX_LIABILITY_ACCOUNT_MASTER_CATEGORY ON LIABILITY_ACCOUNT_MASTER (LIABILITY_CATEGORY);


-- -----------------------------------------------------------------------------
-- LIABILITY_TERM_DEPOSIT_DETAILS: 1:1 detail for LIABILITY_CATEGORY = 'Term Deposits'.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_TERM_DEPOSIT_DETAILS (
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL PRIMARY KEY,
    DEPOSIT_AMOUNT        NUMERIC(18,2),
    INTEREST_RATE         NUMERIC(6,3),
    TENURE_MONTHS         INT,
    MATURITY_DATE         DATE,
    AUTO_RENEWAL_FLAG     CHAR(1)      DEFAULT 'N',
    PAYOUT_FREQUENCY      VARCHAR(20),  -- Monthly / Quarterly / Cumulative
    CREATED_DATE          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE          TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM         VARCHAR(30),
    CONSTRAINT FK_LIABILITY_TERM_DEPOSIT_DETAILS_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -----------------------------------------------------------------------------
-- LIABILITY_CURRENT_ACCOUNT_DETAILS: 1:1 detail for LIABILITY_CATEGORY = 'Current Accounts'.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_CURRENT_ACCOUNT_DETAILS (
    LIABILITY_ACCOUNT_ID      BIGINT       NOT NULL PRIMARY KEY,
    AVERAGE_MONTHLY_BALANCE   NUMERIC(18,2),
    MINIMUM_BALANCE_REQUIRED  NUMERIC(18,2),
    OVERDRAFT_LIMIT           NUMERIC(18,2),
    CREATED_DATE              TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE              TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM             VARCHAR(30),
    CONSTRAINT FK_LIABILITY_CURRENT_ACCOUNT_DETAILS_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -----------------------------------------------------------------------------
-- LIABILITY_BORROWING_DETAILS: 1:1 detail for LIABILITY_CATEGORY = 'Borrowings'.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_BORROWING_DETAILS (
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL PRIMARY KEY,
    BORROWING_TYPE        VARCHAR(30),  -- TermLoanTaken / CCBorrowing / Refinance
    LENDER_NAME           VARCHAR(150),
    PRINCIPAL_AMOUNT      NUMERIC(18,2),
    INTEREST_RATE         NUMERIC(6,3),
    REPAYMENT_TERMS       VARCHAR(300),
    CREATED_DATE          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE          TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM         VARCHAR(30),
    CONSTRAINT FK_LIABILITY_BORROWING_DETAILS_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -----------------------------------------------------------------------------
-- LIABILITY_BOND_DETAILS: 1:1 detail for LIABILITY_CATEGORY = 'Bonds' (bonds
-- issued by the bank / raised as liability funding, not client investments).
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_BOND_DETAILS (
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL PRIMARY KEY,
    BOND_TYPE             VARCHAR(30),
    ISIN_CODE             VARCHAR(12),
    ISSUE_DATE            DATE,
    FACE_VALUE            NUMERIC(18,2),
    COUPON_RATE           NUMERIC(6,3),
    MATURITY_DATE         DATE,
    CREATED_DATE          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE          TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM         VARCHAR(30),
    CONSTRAINT FK_LIABILITY_BOND_DETAILS_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -----------------------------------------------------------------------------
-- LIABILITY_MATURITY_PROFILE: pre-bucketed maturity amounts per account.
-- MATURITY_BUCKET values match src/chart_generator.py's Liability Maturity
-- Profile chart exactly. APR_CLIENT_CODE is denormalized for direct
-- client-level GROUP BY without joining through the account master.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_MATURITY_PROFILE (
    MATURITY_PROFILE_ID   BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    LIABILITY_ACCOUNT_ID  BIGINT       NOT NULL,
    APR_CLIENT_CODE       VARCHAR(14)  NOT NULL,
    AS_OF_DATE            DATE         NOT NULL,
    MATURITY_BUCKET       VARCHAR(10)  NOT NULL,  -- <1Y / 1-3Y / 3-5Y / >5Y
    BUCKET_AMOUNT         NUMERIC(18,2) NOT NULL,
    CREATED_DATE          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE          TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM         VARCHAR(30),
    CONSTRAINT FK_LIABILITY_MATURITY_PROFILE_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    CONSTRAINT FK_LIABILITY_MATURITY_PROFILE_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_LIABILITY_MATURITY_PROFILE_CLIENT ON LIABILITY_MATURITY_PROFILE (APR_CLIENT_CODE, AS_OF_DATE);


-- -----------------------------------------------------------------------------
-- LIABILITY_INTEREST_RATE_HISTORY: rate change history per account.
-- RATE_BUCKET is pre-computed to match src/chart_generator.py's Interest Rate
-- Exposure chart buckets exactly, avoiding runtime bucketing logic in the
-- app or the LLM layer.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_INTEREST_RATE_HISTORY (
    RATE_HISTORY_ID        BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    LIABILITY_ACCOUNT_ID   BIGINT       NOT NULL,
    APR_CLIENT_CODE        VARCHAR(14)  NOT NULL,
    EFFECTIVE_DATE         DATE         NOT NULL,
    INTEREST_RATE          NUMERIC(6,3) NOT NULL,
    RATE_TYPE              VARCHAR(10),  -- Fixed / Floating
    RATE_BUCKET            VARCHAR(20),  -- Fixed <5% / Fixed 5-7% / Fixed >7% / Floating
    CREATED_DATE           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE           TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM          VARCHAR(30),
    CONSTRAINT FK_LIABILITY_INTEREST_RATE_HISTORY_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    CONSTRAINT FK_LIABILITY_INTEREST_RATE_HISTORY_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_LIABILITY_INTEREST_RATE_HISTORY_CLIENT ON LIABILITY_INTEREST_RATE_HISTORY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- LIABILITY_VALUE_HISTORY: monthly total liability value per account, for
-- trend views (mirrors ASSET_VALUE_HISTORY in 02_Asset_Base.sql).
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_VALUE_HISTORY (
    VALUE_HISTORY_ID       BIGINT        NOT NULL PRIMARY KEY AUTO_INCREMENT,
    LIABILITY_ACCOUNT_ID   BIGINT        NOT NULL,
    APR_CLIENT_CODE        VARCHAR(14)   NOT NULL,
    AS_OF_DATE             DATE          NOT NULL,
    LIABILITY_VALUE        NUMERIC(18,2) NOT NULL,
    CURRENCY_CODE          VARCHAR(3),
    CREATED_DATE           TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE           TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM          VARCHAR(30),
    CONSTRAINT FK_LIABILITY_VALUE_HISTORY_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID),
    CONSTRAINT FK_LIABILITY_VALUE_HISTORY_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_LIABILITY_VALUE_HISTORY_CURRENCY_CODE FOREIGN KEY (CURRENCY_CODE) REFERENCES CURRENCY_MASTER(CURRENCY_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_LIABILITY_VALUE_HISTORY_CLIENT_DATE ON LIABILITY_VALUE_HISTORY (APR_CLIENT_CODE, AS_OF_DATE);


-- -----------------------------------------------------------------------------
-- LIABILITY_RISK_METRICS: concentration/funding-stability risk indicators.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_RISK_METRICS (
    RISK_METRIC_ID                  BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    LIABILITY_ACCOUNT_ID            BIGINT       NOT NULL,
    AS_OF_DATE                      DATE         NOT NULL,
    CONCENTRATION_RISK_PERCENTAGE   NUMERIC(5,2),
    FUNDING_STABILITY_RATING        VARCHAR(10),
    CREATED_DATE                    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE                    TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM                   VARCHAR(30),
    CONSTRAINT FK_LIABILITY_RISK_METRICS_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -----------------------------------------------------------------------------
-- LIABILITY_RENEWAL_HISTORY: term-deposit/borrowing renewal events.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_RENEWAL_HISTORY (
    RENEWAL_ID              BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    LIABILITY_ACCOUNT_ID    BIGINT       NOT NULL,
    ORIGINAL_MATURITY_DATE  DATE,
    RENEWED_MATURITY_DATE   DATE,
    RENEWAL_DATE            DATE,
    RENEWED_AMOUNT          NUMERIC(18,2),
    CREATED_DATE            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE            TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM           VARCHAR(30),
    CONSTRAINT FK_LIABILITY_RENEWAL_HISTORY_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -----------------------------------------------------------------------------
-- LIABILITY_EARLY_CLOSURE_HISTORY: premature closure events and penalties.
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_EARLY_CLOSURE_HISTORY (
    CLOSURE_ID             BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    LIABILITY_ACCOUNT_ID   BIGINT       NOT NULL,
    CLOSURE_DATE           DATE,
    CLOSURE_AMOUNT         NUMERIC(18,2),
    PENALTY_AMOUNT         NUMERIC(18,2),
    CLOSURE_REASON         VARCHAR(300),
    CREATED_DATE           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE           TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM          VARCHAR(30),
    CONSTRAINT FK_LIABILITY_EARLY_CLOSURE_HISTORY_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -----------------------------------------------------------------------------
-- LIABILITY_NOMINATION_DETAILS: nominee(s) registered against a liability
-- account (primarily relevant to deposit-type accounts).
-- -----------------------------------------------------------------------------
CREATE TABLE LIABILITY_NOMINATION_DETAILS (
    NOMINATION_ID          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    LIABILITY_ACCOUNT_ID   BIGINT       NOT NULL,
    NOMINEE_NAME           VARCHAR(150),
    RELATIONSHIP           VARCHAR(50),
    SHARE_PERCENTAGE       NUMERIC(5,2),
    CREATED_DATE           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE           TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM          VARCHAR(30),
    CONSTRAINT FK_LIABILITY_NOMINATION_DETAILS_LIABILITY_ACCOUNT_ID FOREIGN KEY (LIABILITY_ACCOUNT_ID) REFERENCES LIABILITY_ACCOUNT_MASTER(LIABILITY_ACCOUNT_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
