-- =============================================================================
-- FILE:        05_RM_Details_Interactions.sql
-- TAB:         RM Details & Interactions
-- SCOPE:       The assigned Relationship Manager's performance, rolled-up
--              interaction stats, visit plans, escalations, and feedback for
--              a client. This tab does NOT own raw call/meeting/communication
--              logs -- those live in CMS (01_CMS.sql) and are referenced here.
-- OWNS:        RM_PERFORMANCE_METRICS, RM_INTERACTION_SUMMARY,
--              RM_CLIENT_VISIT_PLAN, RM_ESCALATION_LOG,
--              RM_TRAINING_CERTIFICATION, RM_TARGET_ACHIEVEMENT,
--              RM_CLIENT_FEEDBACK
-- REFERENCES:  CLIENT_MASTER, RM_MASTER, CLIENT_RM_MAPPING
--              (see 00_Master_Tables.sql) -- not redefined here.
--              CMS_CALL_LOG, CMS_MEETING_RECORD, CMS_COMMUNICATION_LOG
--              (see 01_CMS.sql) -- RM_INTERACTION_SUMMARY rolls these up,
--              it does not duplicate their rows.
--
-- DESIGN NOTE: the current RM assignment for a client is CLIENT_RM_MAPPING
-- (see 00_Master_Tables.sql) -- it is intentionally NOT redefined here.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- RM_PERFORMANCE_METRICS: periodic RM performance metrics against a client
-- relationship (wallet share, revenue contribution, cross-sell ratio, etc).
-- -----------------------------------------------------------------------------
CREATE TABLE RM_PERFORMANCE_METRICS (
    METRIC_ID          BIGINT       NOT NULL PRIMARY KEY,
    RM_CODE             VARCHAR(7)  NOT NULL REFERENCES RM_MASTER(RM_CODE),
    APR_CLIENT_CODE     VARCHAR(14) NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    AS_OF_DATE          DATE        NOT NULL,
    METRIC_TYPE         VARCHAR(30),  -- WalletShare / RevenueContribution / CrossSellRatio
    METRIC_VALUE        NUMERIC(18,2),
    CREATED_DATE        TIMESTAMP   NOT NULL,
    UPDATED_DATE        TIMESTAMP,
    SOURCE_SYSTEM       VARCHAR(30)
);

CREATE INDEX IX_RM_PERFORMANCE_METRICS_CLIENT ON RM_PERFORMANCE_METRICS (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_INTERACTION_SUMMARY: pre-aggregated interaction counts for a client over
-- a period, sourced from CMS_CALL_LOG / CMS_MEETING_RECORD /
-- CMS_COMMUNICATION_LOG (see 01_CMS.sql). Computed by an ETL/rollup job, not
-- duplicated raw data -- keeps this tab's headline query to a single-row
-- lookup instead of aggregating three CMS tables live on every page load.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_INTERACTION_SUMMARY (
    SUMMARY_ID              BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE         VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE                 VARCHAR(7)   NOT NULL REFERENCES RM_MASTER(RM_CODE),
    PERIOD_START_DATE       DATE         NOT NULL,
    PERIOD_END_DATE         DATE         NOT NULL,
    TOTAL_CALLS_COUNT       INT,          -- rolled up from CMS_CALL_LOG
    TOTAL_MEETINGS_COUNT    INT,          -- rolled up from CMS_MEETING_RECORD
    TOTAL_EMAILS_COUNT      INT,          -- rolled up from CMS_COMMUNICATION_LOG
    LAST_INTERACTION_DATE   DATE,
    CREATED_DATE            TIMESTAMP    NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);

CREATE INDEX IX_RM_INTERACTION_SUMMARY_CLIENT ON RM_INTERACTION_SUMMARY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_CLIENT_VISIT_PLAN: planned/completed client visits.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_CLIENT_VISIT_PLAN (
    VISIT_ID          BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE           VARCHAR(7)   NOT NULL REFERENCES RM_MASTER(RM_CODE),
    PLANNED_DATE      DATE         NOT NULL,
    VISIT_PURPOSE     VARCHAR(200),
    VISIT_STATUS      VARCHAR(20),  -- Planned / Completed / Cancelled
    CREATED_DATE      TIMESTAMP    NOT NULL,
    UPDATED_DATE      TIMESTAMP,
    SOURCE_SYSTEM     VARCHAR(30)
);

CREATE INDEX IX_RM_CLIENT_VISIT_PLAN_CLIENT ON RM_CLIENT_VISIT_PLAN (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_ESCALATION_LOG: client issues escalated between RMs / up the hierarchy.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_ESCALATION_LOG (
    ESCALATION_ID        BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE      VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE              VARCHAR(7)   NOT NULL REFERENCES RM_MASTER(RM_CODE),
    ESCALATED_TO_RM_CODE VARCHAR(7)   REFERENCES RM_MASTER(RM_CODE),
    ESCALATION_DATE      DATE         NOT NULL,
    ESCALATION_REASON    VARCHAR(300),
    RESOLUTION_STATUS    VARCHAR(20),  -- Open / Resolved
    RESOLUTION_DATE      DATE,
    CREATED_DATE         TIMESTAMP    NOT NULL,
    UPDATED_DATE         TIMESTAMP,
    SOURCE_SYSTEM        VARCHAR(30)
);

CREATE INDEX IX_RM_ESCALATION_LOG_CLIENT ON RM_ESCALATION_LOG (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_TRAINING_CERTIFICATION: RM's professional certifications (not client-
-- scoped -- keyed by RM only).
-- -----------------------------------------------------------------------------
CREATE TABLE RM_TRAINING_CERTIFICATION (
    CERTIFICATION_ID    BIGINT       NOT NULL PRIMARY KEY,
    RM_CODE              VARCHAR(7)  NOT NULL REFERENCES RM_MASTER(RM_CODE),
    CERTIFICATION_NAME   VARCHAR(150),
    CERTIFICATION_DATE   DATE,
    EXPIRY_DATE          DATE,
    CREATED_DATE         TIMESTAMP   NOT NULL,
    UPDATED_DATE         TIMESTAMP,
    SOURCE_SYSTEM        VARCHAR(30)
);

CREATE INDEX IX_RM_TRAINING_CERTIFICATION_RM ON RM_TRAINING_CERTIFICATION (RM_CODE);


-- -----------------------------------------------------------------------------
-- RM_TARGET_ACHIEVEMENT: RM's periodic business targets vs. achievement
-- (not client-scoped -- keyed by RM only).
-- -----------------------------------------------------------------------------
CREATE TABLE RM_TARGET_ACHIEVEMENT (
    TARGET_ID        BIGINT       NOT NULL PRIMARY KEY,
    RM_CODE           VARCHAR(7)  NOT NULL REFERENCES RM_MASTER(RM_CODE),
    PERIOD_LABEL      VARCHAR(20),  -- e.g. Q1-FY26
    TARGET_TYPE       VARCHAR(30),
    TARGET_VALUE      NUMERIC(18,2),
    ACHIEVED_VALUE    NUMERIC(18,2),
    CREATED_DATE      TIMESTAMP    NOT NULL,
    UPDATED_DATE      TIMESTAMP,
    SOURCE_SYSTEM     VARCHAR(30)
);

CREATE INDEX IX_RM_TARGET_ACHIEVEMENT_RM ON RM_TARGET_ACHIEVEMENT (RM_CODE);


-- -----------------------------------------------------------------------------
-- RM_CLIENT_FEEDBACK: client satisfaction feedback on the RM relationship.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_CLIENT_FEEDBACK (
    FEEDBACK_ID         BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE     VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE             VARCHAR(7)   NOT NULL REFERENCES RM_MASTER(RM_CODE),
    FEEDBACK_DATE       DATE         NOT NULL,
    RATING              SMALLINT,     -- 1-5
    FEEDBACK_COMMENTS   VARCHAR(1000),
    CREATED_DATE        TIMESTAMP    NOT NULL,
    UPDATED_DATE        TIMESTAMP,
    SOURCE_SYSTEM       VARCHAR(30)
);

CREATE INDEX IX_RM_CLIENT_FEEDBACK_CLIENT ON RM_CLIENT_FEEDBACK (APR_CLIENT_CODE);
