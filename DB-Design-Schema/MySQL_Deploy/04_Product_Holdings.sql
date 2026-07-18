-- =============================================================================
-- MariaDB/MySQL deployment copy, generated from ../04_Product_Holdings.sql for the local
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
-- The design source (../04_Product_Holdings.sql) remains the source of truth for schema
-- design; this file is a build artifact of it, not hand-maintained.
-- =============================================================================

-- =============================================================================
-- FILE:        04_Product_Holdings.sql
-- TAB:         Product Holdings
-- SCOPE:       Cross-product view of what a client holds across the bank
--              (spanning Asset/Liability/CMS product lines): utilization,
--              cross-sell opportunities, fee income, relationship depth,
--              channel adoption, and service requests.
-- OWNS:        PRODUCT_HOLDING_SUMMARY, PRODUCT_UTILIZATION,
--              PRODUCT_UTILIZATION_HISTORY, PRODUCT_CROSS_SELL_OPPORTUNITY,
--              PRODUCT_FEE_INCOME, PRODUCT_RELATIONSHIP_DEPTH_SCORE,
--              PRODUCT_CATALOG_FEATURE, PRODUCT_PRICING_TERMS,
--              PRODUCT_CHANNEL_USAGE, PRODUCT_SERVICE_REQUEST
-- REFERENCES:  CLIENT_MASTER, PRODUCT_MASTER, RM_MASTER, CURRENCY_MASTER
--              (see 00_Master_Tables.sql) -- not redefined here.
--
-- DESIGN NOTE: PRODUCT_HOLDING_SUMMARY is a lightweight cross-product index
-- (one row per client+product ever held) -- it does NOT duplicate the
-- detailed asset/liability account data owned by 02_Asset_Base.sql /
-- 03_Liability_Base.sql; it exists purely to answer "what does this client
-- hold across the whole bank" without unioning every product-specific table.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- PRODUCT_HOLDING_SUMMARY: one row per client+product relationship.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_HOLDING_SUMMARY (
    HOLDING_ID          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE     VARCHAR(14)  NOT NULL,
    PRODUCT_CODE        VARCHAR(10)  NOT NULL,
    HOLDING_STATUS      VARCHAR(20)  NOT NULL,  -- Active / Inactive / Dormant
    ACTIVATION_DATE     DATE,
    CLOSURE_DATE        DATE,
    CREATED_DATE        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE        TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM       VARCHAR(30),
    CONSTRAINT FK_PRODUCT_HOLDING_SUMMARY_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_PRODUCT_HOLDING_SUMMARY_PRODUCT_CODE FOREIGN KEY (PRODUCT_CODE) REFERENCES PRODUCT_MASTER(PRODUCT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_HOLDING_SUMMARY_CLIENT ON PRODUCT_HOLDING_SUMMARY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_UTILIZATION: current sanctioned vs. utilized value per holding.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_UTILIZATION (
    UTILIZATION_ID          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    HOLDING_ID              BIGINT       NOT NULL,
    AS_OF_DATE              DATE         NOT NULL,
    SANCTIONED_VALUE        NUMERIC(18,2),
    UTILIZED_VALUE          NUMERIC(18,2),
    UTILIZATION_PERCENTAGE  NUMERIC(5,2),
    CREATED_DATE            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE            TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM           VARCHAR(30),
    CONSTRAINT FK_PRODUCT_UTILIZATION_HOLDING_ID FOREIGN KEY (HOLDING_ID) REFERENCES PRODUCT_HOLDING_SUMMARY(HOLDING_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_UTILIZATION_HOLDING ON PRODUCT_UTILIZATION (HOLDING_ID);


-- -----------------------------------------------------------------------------
-- PRODUCT_UTILIZATION_HISTORY: monthly utilization trend per holding.
-- APR_CLIENT_CODE denormalized for direct client-level trend queries.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_UTILIZATION_HISTORY (
    UTILIZATION_HISTORY_ID  BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    HOLDING_ID              BIGINT       NOT NULL,
    APR_CLIENT_CODE         VARCHAR(14)  NOT NULL,
    AS_OF_DATE              DATE         NOT NULL,
    UTILIZATION_PERCENTAGE  NUMERIC(5,2),
    CREATED_DATE            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE            TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM           VARCHAR(30),
    CONSTRAINT FK_PRODUCT_UTILIZATION_HISTORY_HOLDING_ID FOREIGN KEY (HOLDING_ID) REFERENCES PRODUCT_HOLDING_SUMMARY(HOLDING_ID),
    CONSTRAINT FK_PRODUCT_UTILIZATION_HISTORY_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_UTILIZATION_HISTORY_CLIENT ON PRODUCT_UTILIZATION_HISTORY (APR_CLIENT_CODE, AS_OF_DATE);


-- -----------------------------------------------------------------------------
-- PRODUCT_CROSS_SELL_OPPORTUNITY: identified opportunities to sell a product
-- the client does not currently hold.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_CROSS_SELL_OPPORTUNITY (
    OPPORTUNITY_ID         BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE        VARCHAR(14)  NOT NULL,
    PRODUCT_CODE           VARCHAR(10)  NOT NULL,
    IDENTIFIED_DATE        DATE         NOT NULL,
    IDENTIFIED_BY_RM_CODE  VARCHAR(7),
    OPPORTUNITY_STATUS     VARCHAR(20),  -- Open / Converted / Rejected
    POTENTIAL_VALUE        NUMERIC(18,2),
    CREATED_DATE           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE           TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM          VARCHAR(30),
    CONSTRAINT FK_PRODUCT_CROSS_SELL_OPPORTUNITY_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_PRODUCT_CROSS_SELL_OPPORTUNITY_PRODUCT_CODE FOREIGN KEY (PRODUCT_CODE) REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    CONSTRAINT FK_PRODUCT_CROSS_SELL_OPPORTUNITY_IDENTIFIED_BY_RM_CODE FOREIGN KEY (IDENTIFIED_BY_RM_CODE) REFERENCES RM_MASTER(RM_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_CROSS_SELL_OPPORTUNITY_CLIENT ON PRODUCT_CROSS_SELL_OPPORTUNITY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_FEE_INCOME: fee/commission income earned per holding.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_FEE_INCOME (
    FEE_ID           BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    HOLDING_ID       BIGINT       NOT NULL,
    FEE_TYPE         VARCHAR(50),
    FEE_DATE         DATE         NOT NULL,
    FEE_AMOUNT       NUMERIC(18,2),
    CURRENCY_CODE    VARCHAR(3),
    CREATED_DATE     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE     TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM    VARCHAR(30),
    CONSTRAINT FK_PRODUCT_FEE_INCOME_HOLDING_ID FOREIGN KEY (HOLDING_ID) REFERENCES PRODUCT_HOLDING_SUMMARY(HOLDING_ID),
    CONSTRAINT FK_PRODUCT_FEE_INCOME_CURRENCY_CODE FOREIGN KEY (CURRENCY_CODE) REFERENCES CURRENCY_MASTER(CURRENCY_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_FEE_INCOME_HOLDING ON PRODUCT_FEE_INCOME (HOLDING_ID);


-- -----------------------------------------------------------------------------
-- PRODUCT_RELATIONSHIP_DEPTH_SCORE: periodic composite score of how deep the
-- overall banking relationship is (product count, share of wallet, etc).
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_RELATIONSHIP_DEPTH_SCORE (
    SCORE_ID              BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE       VARCHAR(14)  NOT NULL,
    AS_OF_DATE            DATE         NOT NULL,
    ACTIVE_PRODUCT_COUNT  INT,
    RELATIONSHIP_SCORE    NUMERIC(5,2),
    RELATIONSHIP_TIER     VARCHAR(20),
    CREATED_DATE          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE          TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM         VARCHAR(30),
    CONSTRAINT FK_PRODUCT_RELATIONSHIP_DEPTH_SCORE_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_RELATIONSHIP_DEPTH_SCORE_CLIENT ON PRODUCT_RELATIONSHIP_DEPTH_SCORE (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_CATALOG_FEATURE: marketing/feature copy per product (static
-- reference content, not client-specific).
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_CATALOG_FEATURE (
    FEATURE_ID           BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    PRODUCT_CODE         VARCHAR(10)  NOT NULL,
    FEATURE_NAME         VARCHAR(100),
    FEATURE_DESCRIPTION  VARCHAR(500),
    CREATED_DATE         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE         TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM        VARCHAR(30),
    CONSTRAINT FK_PRODUCT_CATALOG_FEATURE_PRODUCT_CODE FOREIGN KEY (PRODUCT_CODE) REFERENCES PRODUCT_MASTER(PRODUCT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_CATALOG_FEATURE_PRODUCT ON PRODUCT_CATALOG_FEATURE (PRODUCT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_PRICING_TERMS: negotiated pricing terms applied to a holding.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_PRICING_TERMS (
    PRICING_ID       BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    HOLDING_ID       BIGINT       NOT NULL,
    EFFECTIVE_DATE   DATE         NOT NULL,
    PRICING_TYPE     VARCHAR(30),  -- InterestRate / FeeSlab / CommissionRate
    PRICING_VALUE    NUMERIC(10,4),
    CREATED_DATE     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE     TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM    VARCHAR(30),
    CONSTRAINT FK_PRODUCT_PRICING_TERMS_HOLDING_ID FOREIGN KEY (HOLDING_ID) REFERENCES PRODUCT_HOLDING_SUMMARY(HOLDING_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_PRICING_TERMS_HOLDING ON PRODUCT_PRICING_TERMS (HOLDING_ID);


-- -----------------------------------------------------------------------------
-- PRODUCT_CHANNEL_USAGE: digital/branch channel adoption per client.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_CHANNEL_USAGE (
    CHANNEL_USAGE_ID  BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL,
    CHANNEL_NAME      VARCHAR(30)  NOT NULL,  -- NetBanking / MobileApp / API / Branch / RM-Assisted
    USAGE_COUNT       INT,
    LAST_USED_DATE    DATE,
    CREATED_DATE      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE      TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM     VARCHAR(30),
    CONSTRAINT FK_PRODUCT_CHANNEL_USAGE_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_CHANNEL_USAGE_CLIENT ON PRODUCT_CHANNEL_USAGE (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_SERVICE_REQUEST: client-raised service requests tied to a product.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_SERVICE_REQUEST (
    REQUEST_ID        BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL,
    PRODUCT_CODE      VARCHAR(10),
    REQUEST_TYPE      VARCHAR(50),
    REQUEST_DATE      DATE         NOT NULL,
    REQUEST_STATUS    VARCHAR(20),  -- Open / InProgress / Closed
    CLOSURE_DATE      DATE,
    CREATED_DATE      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE      TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM     VARCHAR(30),
    CONSTRAINT FK_PRODUCT_SERVICE_REQUEST_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_PRODUCT_SERVICE_REQUEST_PRODUCT_CODE FOREIGN KEY (PRODUCT_CODE) REFERENCES PRODUCT_MASTER(PRODUCT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_PRODUCT_SERVICE_REQUEST_CLIENT ON PRODUCT_SERVICE_REQUEST (APR_CLIENT_CODE);
