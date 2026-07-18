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
    HOLDING_ID          BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE     VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    PRODUCT_CODE        VARCHAR(10)  NOT NULL REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    HOLDING_STATUS      VARCHAR(20)  NOT NULL,  -- Active / Inactive / Dormant
    ACTIVATION_DATE     DATE,
    CLOSURE_DATE        DATE,
    CREATED_DATE        TIMESTAMP    NOT NULL,
    UPDATED_DATE        TIMESTAMP,
    SOURCE_SYSTEM       VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_HOLDING_SUMMARY_CLIENT ON PRODUCT_HOLDING_SUMMARY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_UTILIZATION: current sanctioned vs. utilized value per holding.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_UTILIZATION (
    UTILIZATION_ID          BIGINT       NOT NULL PRIMARY KEY,
    HOLDING_ID              BIGINT       NOT NULL REFERENCES PRODUCT_HOLDING_SUMMARY(HOLDING_ID),
    AS_OF_DATE              DATE         NOT NULL,
    SANCTIONED_VALUE        NUMERIC(18,2),
    UTILIZED_VALUE          NUMERIC(18,2),
    UTILIZATION_PERCENTAGE  NUMERIC(5,2),
    CREATED_DATE            TIMESTAMP    NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_UTILIZATION_HOLDING ON PRODUCT_UTILIZATION (HOLDING_ID);


-- -----------------------------------------------------------------------------
-- PRODUCT_UTILIZATION_HISTORY: monthly utilization trend per holding.
-- APR_CLIENT_CODE denormalized for direct client-level trend queries.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_UTILIZATION_HISTORY (
    UTILIZATION_HISTORY_ID  BIGINT       NOT NULL PRIMARY KEY,
    HOLDING_ID              BIGINT       NOT NULL REFERENCES PRODUCT_HOLDING_SUMMARY(HOLDING_ID),
    APR_CLIENT_CODE         VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    AS_OF_DATE              DATE         NOT NULL,
    UTILIZATION_PERCENTAGE  NUMERIC(5,2),
    CREATED_DATE            TIMESTAMP    NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_UTILIZATION_HISTORY_CLIENT ON PRODUCT_UTILIZATION_HISTORY (APR_CLIENT_CODE, AS_OF_DATE);


-- -----------------------------------------------------------------------------
-- PRODUCT_CROSS_SELL_OPPORTUNITY: identified opportunities to sell a product
-- the client does not currently hold.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_CROSS_SELL_OPPORTUNITY (
    OPPORTUNITY_ID         BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE        VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    PRODUCT_CODE           VARCHAR(10)  NOT NULL REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    IDENTIFIED_DATE        DATE         NOT NULL,
    IDENTIFIED_BY_RM_CODE  VARCHAR(7)   REFERENCES RM_MASTER(RM_CODE),
    OPPORTUNITY_STATUS     VARCHAR(20),  -- Open / Converted / Rejected
    POTENTIAL_VALUE        NUMERIC(18,2),
    CREATED_DATE           TIMESTAMP    NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_CROSS_SELL_OPPORTUNITY_CLIENT ON PRODUCT_CROSS_SELL_OPPORTUNITY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_FEE_INCOME: fee/commission income earned per holding.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_FEE_INCOME (
    FEE_ID           BIGINT       NOT NULL PRIMARY KEY,
    HOLDING_ID       BIGINT       NOT NULL REFERENCES PRODUCT_HOLDING_SUMMARY(HOLDING_ID),
    FEE_TYPE         VARCHAR(50),
    FEE_DATE         DATE         NOT NULL,
    FEE_AMOUNT       NUMERIC(18,2),
    CURRENCY_CODE    VARCHAR(3)   REFERENCES CURRENCY_MASTER(CURRENCY_CODE),
    CREATED_DATE     TIMESTAMP    NOT NULL,
    UPDATED_DATE     TIMESTAMP,
    SOURCE_SYSTEM    VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_FEE_INCOME_HOLDING ON PRODUCT_FEE_INCOME (HOLDING_ID);


-- -----------------------------------------------------------------------------
-- PRODUCT_RELATIONSHIP_DEPTH_SCORE: periodic composite score of how deep the
-- overall banking relationship is (product count, share of wallet, etc).
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_RELATIONSHIP_DEPTH_SCORE (
    SCORE_ID              BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE       VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    AS_OF_DATE            DATE         NOT NULL,
    ACTIVE_PRODUCT_COUNT  INT,
    RELATIONSHIP_SCORE    NUMERIC(5,2),
    RELATIONSHIP_TIER     VARCHAR(20),
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_RELATIONSHIP_DEPTH_SCORE_CLIENT ON PRODUCT_RELATIONSHIP_DEPTH_SCORE (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_CATALOG_FEATURE: marketing/feature copy per product (static
-- reference content, not client-specific).
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_CATALOG_FEATURE (
    FEATURE_ID           BIGINT       NOT NULL PRIMARY KEY,
    PRODUCT_CODE         VARCHAR(10)  NOT NULL REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    FEATURE_NAME         VARCHAR(100),
    FEATURE_DESCRIPTION  VARCHAR(500),
    CREATED_DATE         TIMESTAMP    NOT NULL,
    UPDATED_DATE         TIMESTAMP,
    SOURCE_SYSTEM        VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_CATALOG_FEATURE_PRODUCT ON PRODUCT_CATALOG_FEATURE (PRODUCT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_PRICING_TERMS: negotiated pricing terms applied to a holding.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_PRICING_TERMS (
    PRICING_ID       BIGINT       NOT NULL PRIMARY KEY,
    HOLDING_ID       BIGINT       NOT NULL REFERENCES PRODUCT_HOLDING_SUMMARY(HOLDING_ID),
    EFFECTIVE_DATE   DATE         NOT NULL,
    PRICING_TYPE     VARCHAR(30),  -- InterestRate / FeeSlab / CommissionRate
    PRICING_VALUE    NUMERIC(10,4),
    CREATED_DATE     TIMESTAMP    NOT NULL,
    UPDATED_DATE     TIMESTAMP,
    SOURCE_SYSTEM    VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_PRICING_TERMS_HOLDING ON PRODUCT_PRICING_TERMS (HOLDING_ID);


-- -----------------------------------------------------------------------------
-- PRODUCT_CHANNEL_USAGE: digital/branch channel adoption per client.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_CHANNEL_USAGE (
    CHANNEL_USAGE_ID  BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CHANNEL_NAME      VARCHAR(30)  NOT NULL,  -- NetBanking / MobileApp / API / Branch / RM-Assisted
    USAGE_COUNT       INT,
    LAST_USED_DATE    DATE,
    CREATED_DATE      TIMESTAMP    NOT NULL,
    UPDATED_DATE      TIMESTAMP,
    SOURCE_SYSTEM     VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_CHANNEL_USAGE_CLIENT ON PRODUCT_CHANNEL_USAGE (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_SERVICE_REQUEST: client-raised service requests tied to a product.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_SERVICE_REQUEST (
    REQUEST_ID        BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    PRODUCT_CODE      VARCHAR(10)  REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    REQUEST_TYPE      VARCHAR(50),
    REQUEST_DATE      DATE         NOT NULL,
    REQUEST_STATUS    VARCHAR(20),  -- Open / InProgress / Closed
    CLOSURE_DATE      DATE,
    CREATED_DATE      TIMESTAMP    NOT NULL,
    UPDATED_DATE      TIMESTAMP,
    SOURCE_SYSTEM     VARCHAR(30)
);

CREATE INDEX IX_PRODUCT_SERVICE_REQUEST_CLIENT ON PRODUCT_SERVICE_REQUEST (APR_CLIENT_CODE);
