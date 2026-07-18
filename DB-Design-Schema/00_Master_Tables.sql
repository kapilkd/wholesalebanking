-- =============================================================================
-- FILE:        00_Master_Tables.sql
-- SCOPE:       Shared reference/master data used by ALL tab schemas.
-- OWNS:        BRANCH_MASTER, CURRENCY_MASTER, INDUSTRY_SECTOR_MASTER,
--              RM_MASTER, CLIENT_MASTER, PRODUCT_MASTER, CLIENT_RM_MAPPING,
--              ACCOUNT_MASTER
-- REFERENCED BY: 01_CMS.sql, 02_Asset_Base.sql, 03_Liability_Base.sql,
--              04_Product_Holdings.sql, 05_RM_Details_Interactions.sql,
--              06_RM_Discussion.sql
--
-- RULE: These tables are defined ONLY here. Every other file references them
--       via FOREIGN KEY + a "-- see 00_Master_Tables.sql" comment; they must
--       never be redefined elsewhere.
--
-- CONVENTIONS (apply to every file in DB-Design-Schema/):
--   - UPPER_SNAKE_CASE for all tables/columns, domain-prefixed (CMS_, ASSET_,
--     LIABILITY_, PRODUCT_, RM_).
--   - Surrogate PKs are declared BIGINT PRIMARY KEY. Auto-increment mechanism
--     (IDENTITY / SERIAL / SEQUENCE) is engine-specific and added at
--     deployment time, intentionally omitted here for portability.
--   - Every client-scoped table carries APR_CLIENT_CODE NOT NULL plus a
--     leading index on it -- this is the primary performance lever for
--     keeping multi-table joins sub-second when queries are always filtered
--     by client.
--   - Every table ends with the audit columns: CREATED_DATE, UPDATED_DATE,
--     SOURCE_SYSTEM.
--   - Portable ANSI SQL only: VARCHAR, NUMERIC, DATE, TIME, TIMESTAMP,
--     SMALLINT, INT, BIGINT, CHAR(1) for boolean-style flags.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- BRANCH_MASTER: physical/booking branch reference data.
-- -----------------------------------------------------------------------------
CREATE TABLE BRANCH_MASTER (
    BRANCH_CODE      VARCHAR(10)  NOT NULL PRIMARY KEY,
    BRANCH_NAME      VARCHAR(100) NOT NULL,
    REGION           VARCHAR(50),
    ZONE             VARCHAR(50),
    ADDRESS_LINE1    VARCHAR(150),
    CITY             VARCHAR(50),
    STATE            VARCHAR(50),
    COUNTRY          VARCHAR(50),
    PIN_CODE         VARCHAR(10),
    CREATED_DATE     TIMESTAMP    NOT NULL,
    UPDATED_DATE     TIMESTAMP,
    SOURCE_SYSTEM    VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- CURRENCY_MASTER: ISO currency reference data.
-- -----------------------------------------------------------------------------
CREATE TABLE CURRENCY_MASTER (
    CURRENCY_CODE      VARCHAR(3)  NOT NULL PRIMARY KEY,  -- ISO 4217, e.g. INR/USD
    CURRENCY_NAME      VARCHAR(50) NOT NULL,
    CURRENCY_SYMBOL    VARCHAR(5),
    DECIMAL_PRECISION  SMALLINT    DEFAULT 2,
    CREATED_DATE       TIMESTAMP   NOT NULL,
    UPDATED_DATE       TIMESTAMP,
    SOURCE_SYSTEM      VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- INDUSTRY_SECTOR_MASTER: client industry/sector classification.
-- -----------------------------------------------------------------------------
CREATE TABLE INDUSTRY_SECTOR_MASTER (
    SECTOR_CODE      VARCHAR(10)  NOT NULL PRIMARY KEY,
    SECTOR_NAME      VARCHAR(100) NOT NULL,
    NIC_CODE         VARCHAR(10),               -- National Industrial Classification code
    RISK_CATEGORY    VARCHAR(20),               -- Low / Medium / High
    CREATED_DATE     TIMESTAMP    NOT NULL,
    UPDATED_DATE     TIMESTAMP,
    SOURCE_SYSTEM    VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- RM_MASTER: Relationship Manager directory. RM_CODE is 6-7 chars (see app.py).
-- -----------------------------------------------------------------------------
CREATE TABLE RM_MASTER (
    RM_CODE              VARCHAR(7)   NOT NULL PRIMARY KEY,
    RM_NAME              VARCHAR(100) NOT NULL,
    DESIGNATION          VARCHAR(50),
    BRANCH_CODE          VARCHAR(10)  NOT NULL REFERENCES BRANCH_MASTER(BRANCH_CODE),
    EMAIL                VARCHAR(100),
    PHONE_NUMBER         VARCHAR(15),
    REPORTING_RM_CODE    VARCHAR(7)   REFERENCES RM_MASTER(RM_CODE),  -- self-ref: reporting manager
    DATE_OF_JOINING      DATE,
    EMPLOYMENT_STATUS    VARCHAR(20),           -- Active / Inactive
    CREATED_DATE         TIMESTAMP    NOT NULL,
    UPDATED_DATE         TIMESTAMP,
    SOURCE_SYSTEM        VARCHAR(30)
);

CREATE INDEX IX_RM_MASTER_BRANCH ON RM_MASTER (BRANCH_CODE);


-- -----------------------------------------------------------------------------
-- CLIENT_MASTER: wholesale banking client (corporate) master.
-- APR_CLIENT_CODE is 8-14 chars, e.g. APR12345678 (see app.py).
-- -----------------------------------------------------------------------------
CREATE TABLE CLIENT_MASTER (
    APR_CLIENT_CODE       VARCHAR(14)  NOT NULL PRIMARY KEY,
    CLIENT_NAME           VARCHAR(200) NOT NULL,
    CONSTITUTION_TYPE     VARCHAR(50),           -- Pvt Ltd / Public Ltd / Partnership / Proprietorship
    PAN_NUMBER            VARCHAR(10),
    CIN_NUMBER            VARCHAR(21),
    SECTOR_CODE           VARCHAR(10)  REFERENCES INDUSTRY_SECTOR_MASTER(SECTOR_CODE),
    HOME_BRANCH_CODE      VARCHAR(10)  REFERENCES BRANCH_MASTER(BRANCH_CODE),
    CLIENT_SEGMENT        VARCHAR(30),           -- Large Corporate / Mid Corporate / Emerging Corporate
    INCORPORATION_DATE    DATE,
    ONBOARDING_DATE       DATE         NOT NULL,
    KYC_STATUS            VARCHAR(20),
    CLIENT_STATUS         VARCHAR(20),           -- Active / Dormant / Closed
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_CLIENT_MASTER_SECTOR ON CLIENT_MASTER (SECTOR_CODE);
CREATE INDEX IX_CLIENT_MASTER_BRANCH ON CLIENT_MASTER (HOME_BRANCH_CODE);


-- -----------------------------------------------------------------------------
-- PRODUCT_MASTER: catalog of every product across Asset / Liability / CMS /
-- Trade Finance / Treasury lines.
-- -----------------------------------------------------------------------------
CREATE TABLE PRODUCT_MASTER (
    PRODUCT_CODE           VARCHAR(10)  NOT NULL PRIMARY KEY,
    PRODUCT_NAME           VARCHAR(100) NOT NULL,
    PRODUCT_CATEGORY       VARCHAR(30)  NOT NULL,  -- Asset / Liability / CMS / TradeFinance / Treasury
    PRODUCT_SUB_CATEGORY   VARCHAR(50),
    GL_CODE                VARCHAR(20),            -- General Ledger code for accounting linkage
    IS_ACTIVE              CHAR(1)      DEFAULT 'Y',
    CREATED_DATE           TIMESTAMP    NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- CLIENT_RM_MAPPING: time-bound history of which RM(s) own a client.
-- Referenced by RM Details tab (05) instead of being redefined there.
-- -----------------------------------------------------------------------------
CREATE TABLE CLIENT_RM_MAPPING (
    CLIENT_RM_MAPPING_ID  BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE       VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE                VARCHAR(7)  NOT NULL REFERENCES RM_MASTER(RM_CODE),
    MAPPING_ROLE           VARCHAR(20),           -- Primary RM / Backup RM / Team Lead
    MAPPING_START_DATE     DATE         NOT NULL,
    MAPPING_END_DATE       DATE,                  -- NULL = currently active mapping
    IS_PRIMARY             CHAR(1)      DEFAULT 'Y',
    CREATED_DATE           TIMESTAMP    NOT NULL,
    UPDATED_DATE           TIMESTAMP,
    SOURCE_SYSTEM          VARCHAR(30)
);

CREATE INDEX IX_CLIENT_RM_MAPPING_CLIENT ON CLIENT_RM_MAPPING (APR_CLIENT_CODE);
CREATE INDEX IX_CLIENT_RM_MAPPING_RM ON CLIENT_RM_MAPPING (RM_CODE);


-- -----------------------------------------------------------------------------
-- ACCOUNT_MASTER: generic account header shared as a join anchor by CMS
-- balance tables. Asset/Liability tabs use their own ASSET_ACCOUNT_MASTER /
-- LIABILITY_ACCOUNT_MASTER (see 02_Asset_Base.sql, 03_Liability_Base.sql)
-- for domain-specific detail -- this table is the bank-wide account registry.
-- -----------------------------------------------------------------------------
CREATE TABLE ACCOUNT_MASTER (
    ACCOUNT_NUMBER        VARCHAR(20)  NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE       VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    PRODUCT_CODE          VARCHAR(10)  NOT NULL REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    BRANCH_CODE           VARCHAR(10)  NOT NULL REFERENCES BRANCH_MASTER(BRANCH_CODE),
    CURRENCY_CODE         VARCHAR(3)   NOT NULL REFERENCES CURRENCY_MASTER(CURRENCY_CODE),
    ACCOUNT_OPEN_DATE     DATE         NOT NULL,
    ACCOUNT_CLOSE_DATE    DATE,
    ACCOUNT_STATUS        VARCHAR(20),           -- Active / Dormant / Closed
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_ACCOUNT_MASTER_CLIENT ON ACCOUNT_MASTER (APR_CLIENT_CODE);
