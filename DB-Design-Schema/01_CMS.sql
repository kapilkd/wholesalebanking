-- =============================================================================
-- FILE:        01_CMS.sql
-- TAB:         CMS (Content/Customer Management)
-- SCOPE:       System of record for customer information, communications,
--              meetings, calls, documents, and account balance history.
--              This is the raw-log/content layer for a client -- other tabs
--              (RM Details & Interactions, RM Discussion) reference these
--              tables by FK for their own rollups/structured views rather
--              than duplicating the raw data.
-- OWNS:        CMS_CUSTOMER_PROFILE, CMS_CUSTOMER_ADDRESS, CMS_CUSTOMER_CONTACT,
--              CMS_COMMUNICATION_LOG, CMS_CALL_LOG, CMS_MEETING_RECORD,
--              CMS_DOCUMENT_REPOSITORY, CMS_ACCOUNT_BALANCE_CURRENT,
--              CMS_ACCOUNT_BALANCE_HISTORY, CMS_CUSTOMER_SEGMENT_HISTORY,
--              CMS_NOTES_REMARKS
-- REFERENCES:  CLIENT_MASTER, RM_MASTER, ACCOUNT_MASTER, CURRENCY_MASTER
--              (see 00_Master_Tables.sql) -- not redefined here.
-- REFERENCED BY: 05_RM_Details_Interactions.sql (RM_INTERACTION_SUMMARY rolls
--              up CMS_CALL_LOG / CMS_MEETING_RECORD / CMS_COMMUNICATION_LOG),
--              06_RM_Discussion.sql (RM_DISCUSSION_SESSION links to
--              CMS_MEETING_RECORD when a discussion was logged as a meeting).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- CMS_CUSTOMER_PROFILE: 1:1 extension of CLIENT_MASTER with CMS-specific
-- profile attributes not part of the core client master.
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_CUSTOMER_PROFILE (
    APR_CLIENT_CODE           VARCHAR(14)  NOT NULL PRIMARY KEY REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),  -- see 00_Master_Tables.sql
    GROUP_NAME                VARCHAR(200),
    PARENT_COMPANY_NAME       VARCHAR(200),
    WEBSITE_URL                VARCHAR(200),
    CREDIT_RATING              VARCHAR(10),
    RATING_AGENCY               VARCHAR(50),
    RATING_DATE                 DATE,
    RELATIONSHIP_SINCE_DATE      DATE,
    ANNUAL_TURNOVER_AMOUNT       NUMERIC(18,2),
    CREATED_DATE                 TIMESTAMP    NOT NULL,
    UPDATED_DATE                 TIMESTAMP,
    SOURCE_SYSTEM                VARCHAR(30)
);


-- -----------------------------------------------------------------------------
-- CMS_CUSTOMER_ADDRESS: multiple addresses per client (registered,
-- correspondence, branch/factory, etc).
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_CUSTOMER_ADDRESS (
    ADDRESS_ID        BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    ADDRESS_TYPE      VARCHAR(20)  NOT NULL,  -- Registered / Correspondence / Branch / Factory
    ADDRESS_LINE1     VARCHAR(150),
    ADDRESS_LINE2     VARCHAR(150),
    CITY              VARCHAR(50),
    STATE             VARCHAR(50),
    COUNTRY           VARCHAR(50),
    PIN_CODE          VARCHAR(10),
    IS_PRIMARY        CHAR(1)      DEFAULT 'N',
    CREATED_DATE      TIMESTAMP    NOT NULL,
    UPDATED_DATE      TIMESTAMP,
    SOURCE_SYSTEM     VARCHAR(30)
);

CREATE INDEX IX_CMS_CUSTOMER_ADDRESS_CLIENT ON CMS_CUSTOMER_ADDRESS (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- CMS_CUSTOMER_CONTACT: named contact persons at the client organization.
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_CUSTOMER_CONTACT (
    CONTACT_ID           BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE      VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONTACT_PERSON_NAME  VARCHAR(100) NOT NULL,
    DESIGNATION          VARCHAR(50),
    EMAIL                VARCHAR(100),
    PHONE_NUMBER         VARCHAR(15),
    IS_PRIMARY           CHAR(1)      DEFAULT 'N',
    CREATED_DATE         TIMESTAMP    NOT NULL,
    UPDATED_DATE         TIMESTAMP,
    SOURCE_SYSTEM        VARCHAR(30)
);

CREATE INDEX IX_CMS_CUSTOMER_CONTACT_CLIENT ON CMS_CUSTOMER_CONTACT (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- CMS_COMMUNICATION_LOG: every non-call, non-meeting communication with the
-- client (email, letter, SMS, formal notice).
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_COMMUNICATION_LOG (
    COMMUNICATION_ID         BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE          VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE                  VARCHAR(7)   REFERENCES RM_MASTER(RM_CODE),
    COMMUNICATION_TYPE       VARCHAR(20)  NOT NULL,  -- Email / Letter / SMS / Notice / Fax
    COMMUNICATION_DIRECTION  VARCHAR(10)  NOT NULL,  -- Inbound / Outbound
    COMMUNICATION_DATE       TIMESTAMP    NOT NULL,
    SUBJECT                  VARCHAR(200),
    SUMMARY                  VARCHAR(1000),
    CREATED_DATE             TIMESTAMP    NOT NULL,
    UPDATED_DATE              TIMESTAMP,
    SOURCE_SYSTEM             VARCHAR(30)
);

CREATE INDEX IX_CMS_COMMUNICATION_LOG_CLIENT ON CMS_COMMUNICATION_LOG (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- CMS_CALL_LOG: phone call history with the client.
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_CALL_LOG (
    CALL_ID            BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE    VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE             VARCHAR(7)  REFERENCES RM_MASTER(RM_CODE),
    CALL_DATE           DATE        NOT NULL,
    CALL_TIME           TIME,
    DURATION_MINUTES    INT,
    CALL_TYPE           VARCHAR(10),  -- Incoming / Outgoing
    CALL_PURPOSE        VARCHAR(100),
    CALL_OUTCOME        VARCHAR(200),
    CREATED_DATE        TIMESTAMP     NOT NULL,
    UPDATED_DATE        TIMESTAMP,
    SOURCE_SYSTEM       VARCHAR(30)
);

CREATE INDEX IX_CMS_CALL_LOG_CLIENT ON CMS_CALL_LOG (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- CMS_MEETING_RECORD: logged meetings with the client (any mode).
-- Referenced by RM_DISCUSSION_SESSION (see 06_RM_Discussion.sql) when a
-- discussion is tied to a specific logged meeting.
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_MEETING_RECORD (
    MEETING_ID         BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE    VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE             VARCHAR(7)  REFERENCES RM_MASTER(RM_CODE),
    MEETING_DATE        DATE        NOT NULL,
    MEETING_TYPE        VARCHAR(20),  -- In-Person / Virtual / Telephonic
    LOCATION            VARCHAR(150),
    ATTENDEES           VARCHAR(500),
    AGENDA              VARCHAR(500),
    MINUTES_SUMMARY     VARCHAR(2000),
    CREATED_DATE        TIMESTAMP     NOT NULL,
    UPDATED_DATE        TIMESTAMP,
    SOURCE_SYSTEM       VARCHAR(30)
);

CREATE INDEX IX_CMS_MEETING_RECORD_CLIENT ON CMS_MEETING_RECORD (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- CMS_DOCUMENT_REPOSITORY: KYC/agreement/financial-statement document index.
-- FILE_REFERENCE points to an external document store (blob path / DMS ID),
-- the file content itself is not stored in the relational DB.
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_DOCUMENT_REPOSITORY (
    DOCUMENT_ID         BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE     VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    DOCUMENT_TYPE       VARCHAR(30)  NOT NULL,  -- KYC / Agreement / BoardResolution / FinancialStatement / Other
    DOCUMENT_NAME       VARCHAR(200) NOT NULL,
    UPLOAD_DATE         DATE         NOT NULL,
    EXPIRY_DATE         DATE,
    FILE_REFERENCE      VARCHAR(300),
    DOCUMENT_STATUS     VARCHAR(20),  -- Valid / Expired / PendingRenewal
    CREATED_DATE        TIMESTAMP    NOT NULL,
    UPDATED_DATE        TIMESTAMP,
    SOURCE_SYSTEM       VARCHAR(30)
);

CREATE INDEX IX_CMS_DOCUMENT_REPOSITORY_CLIENT ON CMS_DOCUMENT_REPOSITORY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- CMS_ACCOUNT_BALANCE_CURRENT: latest known balance snapshot per account
-- (1:1 with ACCOUNT_MASTER). APR_CLIENT_CODE is denormalized here so the
-- CMS tab can pull a client's current balances without joining through
-- ACCOUNT_MASTER first.
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_ACCOUNT_BALANCE_CURRENT (
    ACCOUNT_NUMBER       VARCHAR(20)  NOT NULL PRIMARY KEY REFERENCES ACCOUNT_MASTER(ACCOUNT_NUMBER),
    APR_CLIENT_CODE      VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    AS_OF_DATE           DATE         NOT NULL,
    CURRENT_BALANCE      NUMERIC(18,2) NOT NULL,
    AVAILABLE_BALANCE    NUMERIC(18,2),
    HOLD_AMOUNT          NUMERIC(18,2),
    CURRENCY_CODE        VARCHAR(3)   NOT NULL REFERENCES CURRENCY_MASTER(CURRENCY_CODE),
    CREATED_DATE         TIMESTAMP    NOT NULL,
    UPDATED_DATE         TIMESTAMP,
    SOURCE_SYSTEM        VARCHAR(30)
);

CREATE INDEX IX_CMS_ACCOUNT_BALANCE_CURRENT_CLIENT ON CMS_ACCOUNT_BALANCE_CURRENT (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- CMS_ACCOUNT_BALANCE_HISTORY: periodic (e.g. daily/monthly) balance
-- snapshots per account, for trend/history views.
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_ACCOUNT_BALANCE_HISTORY (
    BALANCE_HISTORY_ID  BIGINT       NOT NULL PRIMARY KEY,
    ACCOUNT_NUMBER       VARCHAR(20) NOT NULL REFERENCES ACCOUNT_MASTER(ACCOUNT_NUMBER),
    APR_CLIENT_CODE      VARCHAR(14) NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    BALANCE_DATE         DATE        NOT NULL,
    OPENING_BALANCE      NUMERIC(18,2),
    CLOSING_BALANCE      NUMERIC(18,2),
    CURRENCY_CODE        VARCHAR(3)  NOT NULL REFERENCES CURRENCY_MASTER(CURRENCY_CODE),
    CREATED_DATE         TIMESTAMP   NOT NULL,
    UPDATED_DATE         TIMESTAMP,
    SOURCE_SYSTEM        VARCHAR(30)
);

CREATE INDEX IX_CMS_ACCT_BAL_HISTORY_CLIENT_DATE ON CMS_ACCOUNT_BALANCE_HISTORY (APR_CLIENT_CODE, BALANCE_DATE);


-- -----------------------------------------------------------------------------
-- CMS_CUSTOMER_SEGMENT_HISTORY: time-bound history of client segment
-- reclassification (e.g. Large Corporate -> Mid Corporate).
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_CUSTOMER_SEGMENT_HISTORY (
    SEGMENT_HISTORY_ID     BIGINT      NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE        VARCHAR(14) NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    SEGMENT_CODE            VARCHAR(30) NOT NULL,
    EFFECTIVE_FROM_DATE      DATE       NOT NULL,
    EFFECTIVE_TO_DATE          DATE,               -- NULL = current segment
    CLASSIFIED_BY_RM_CODE       VARCHAR(7) REFERENCES RM_MASTER(RM_CODE),
    CREATED_DATE                 TIMESTAMP NOT NULL,
    UPDATED_DATE                   TIMESTAMP,
    SOURCE_SYSTEM                    VARCHAR(30)
);

CREATE INDEX IX_CMS_CUSTOMER_SEGMENT_HISTORY_CLIENT ON CMS_CUSTOMER_SEGMENT_HISTORY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- CMS_NOTES_REMARKS: free-text RM/ops notes against a client not tied to a
-- specific call, meeting, or communication record.
-- -----------------------------------------------------------------------------
CREATE TABLE CMS_NOTES_REMARKS (
    NOTE_ID            BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE    VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE            VARCHAR(7)   REFERENCES RM_MASTER(RM_CODE),
    NOTE_DATE          DATE         NOT NULL,
    NOTE_TYPE          VARCHAR(30),
    NOTE_TEXT          VARCHAR(2000),
    CREATED_DATE       TIMESTAMP    NOT NULL,
    UPDATED_DATE       TIMESTAMP,
    SOURCE_SYSTEM      VARCHAR(30)
);

CREATE INDEX IX_CMS_NOTES_REMARKS_CLIENT ON CMS_NOTES_REMARKS (APR_CLIENT_CODE);
