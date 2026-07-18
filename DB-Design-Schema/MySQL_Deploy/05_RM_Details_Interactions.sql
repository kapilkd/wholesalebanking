-- =============================================================================
-- MariaDB/MySQL deployment copy, generated from ../05_RM_Details_Interactions.sql for the local
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
-- The design source (../05_RM_Details_Interactions.sql) remains the source of truth for schema
-- design; this file is a build artifact of it, not hand-maintained.
-- =============================================================================

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
    METRIC_ID          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    RM_CODE             VARCHAR(7)  NOT NULL,
    APR_CLIENT_CODE     VARCHAR(14) NOT NULL,
    AS_OF_DATE          DATE        NOT NULL,
    METRIC_TYPE         VARCHAR(30),  -- WalletShare / RevenueContribution / CrossSellRatio
    METRIC_VALUE        NUMERIC(18,2),
    CREATED_DATE        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE        TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM       VARCHAR(30),
    CONSTRAINT FK_RM_PERFORMANCE_METRICS_RM_CODE FOREIGN KEY (RM_CODE) REFERENCES RM_MASTER(RM_CODE),
    CONSTRAINT FK_RM_PERFORMANCE_METRICS_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_PERFORMANCE_METRICS_CLIENT ON RM_PERFORMANCE_METRICS (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_INTERACTION_SUMMARY: pre-aggregated interaction counts for a client over
-- a period, sourced from CMS_CALL_LOG / CMS_MEETING_RECORD /
-- CMS_COMMUNICATION_LOG (see 01_CMS.sql). Computed by an ETL/rollup job, not
-- duplicated raw data -- keeps this tab's headline query to a single-row
-- lookup instead of aggregating three CMS tables live on every page load.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_INTERACTION_SUMMARY (
    SUMMARY_ID              BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE         VARCHAR(14)  NOT NULL,
    RM_CODE                 VARCHAR(7)   NOT NULL,
    PERIOD_START_DATE       DATE         NOT NULL,
    PERIOD_END_DATE         DATE         NOT NULL,
    TOTAL_CALLS_COUNT       INT,          -- rolled up from CMS_CALL_LOG
    TOTAL_MEETINGS_COUNT    INT,          -- rolled up from CMS_MEETING_RECORD
    TOTAL_EMAILS_COUNT      INT,          -- rolled up from CMS_COMMUNICATION_LOG
    LAST_INTERACTION_DATE   DATE,
    CREATED_DATE            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE            TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM           VARCHAR(30),
    CONSTRAINT FK_RM_INTERACTION_SUMMARY_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_RM_INTERACTION_SUMMARY_RM_CODE FOREIGN KEY (RM_CODE) REFERENCES RM_MASTER(RM_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_INTERACTION_SUMMARY_CLIENT ON RM_INTERACTION_SUMMARY (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_CLIENT_VISIT_PLAN: planned/completed client visits.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_CLIENT_VISIT_PLAN (
    VISIT_ID          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL,
    RM_CODE           VARCHAR(7)   NOT NULL,
    PLANNED_DATE      DATE         NOT NULL,
    VISIT_PURPOSE     VARCHAR(200),
    VISIT_STATUS      VARCHAR(20),  -- Planned / Completed / Cancelled
    CREATED_DATE      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE      TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM     VARCHAR(30),
    CONSTRAINT FK_RM_CLIENT_VISIT_PLAN_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_RM_CLIENT_VISIT_PLAN_RM_CODE FOREIGN KEY (RM_CODE) REFERENCES RM_MASTER(RM_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_CLIENT_VISIT_PLAN_CLIENT ON RM_CLIENT_VISIT_PLAN (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_ESCALATION_LOG: client issues escalated between RMs / up the hierarchy.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_ESCALATION_LOG (
    ESCALATION_ID        BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE      VARCHAR(14)  NOT NULL,
    RM_CODE              VARCHAR(7)   NOT NULL,
    ESCALATED_TO_RM_CODE VARCHAR(7),
    ESCALATION_DATE      DATE         NOT NULL,
    ESCALATION_REASON    VARCHAR(300),
    RESOLUTION_STATUS    VARCHAR(20),  -- Open / Resolved
    RESOLUTION_DATE      DATE,
    CREATED_DATE         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE         TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM        VARCHAR(30),
    CONSTRAINT FK_RM_ESCALATION_LOG_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_RM_ESCALATION_LOG_RM_CODE FOREIGN KEY (RM_CODE) REFERENCES RM_MASTER(RM_CODE),
    CONSTRAINT FK_RM_ESCALATION_LOG_ESCALATED_TO_RM_CODE FOREIGN KEY (ESCALATED_TO_RM_CODE) REFERENCES RM_MASTER(RM_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_ESCALATION_LOG_CLIENT ON RM_ESCALATION_LOG (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_TRAINING_CERTIFICATION: RM's professional certifications (not client-
-- scoped -- keyed by RM only).
-- -----------------------------------------------------------------------------
CREATE TABLE RM_TRAINING_CERTIFICATION (
    CERTIFICATION_ID    BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    RM_CODE              VARCHAR(7)  NOT NULL,
    CERTIFICATION_NAME   VARCHAR(150),
    CERTIFICATION_DATE   DATE,
    EXPIRY_DATE          DATE,
    CREATED_DATE         TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE         TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM        VARCHAR(30),
    CONSTRAINT FK_RM_TRAINING_CERTIFICATION_RM_CODE FOREIGN KEY (RM_CODE) REFERENCES RM_MASTER(RM_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_TRAINING_CERTIFICATION_RM ON RM_TRAINING_CERTIFICATION (RM_CODE);


-- -----------------------------------------------------------------------------
-- RM_TARGET_ACHIEVEMENT: RM's periodic business targets vs. achievement
-- (not client-scoped -- keyed by RM only).
-- -----------------------------------------------------------------------------
CREATE TABLE RM_TARGET_ACHIEVEMENT (
    TARGET_ID        BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    RM_CODE           VARCHAR(7)  NOT NULL,
    PERIOD_LABEL      VARCHAR(20),  -- e.g. Q1-FY26
    TARGET_TYPE       VARCHAR(30),
    TARGET_VALUE      NUMERIC(18,2),
    ACHIEVED_VALUE    NUMERIC(18,2),
    CREATED_DATE      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE      TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM     VARCHAR(30),
    CONSTRAINT FK_RM_TARGET_ACHIEVEMENT_RM_CODE FOREIGN KEY (RM_CODE) REFERENCES RM_MASTER(RM_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_TARGET_ACHIEVEMENT_RM ON RM_TARGET_ACHIEVEMENT (RM_CODE);


-- -----------------------------------------------------------------------------
-- RM_CLIENT_FEEDBACK: client satisfaction feedback on the RM relationship.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_CLIENT_FEEDBACK (
    FEEDBACK_ID         BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE     VARCHAR(14)  NOT NULL,
    RM_CODE             VARCHAR(7)   NOT NULL,
    FEEDBACK_DATE       DATE         NOT NULL,
    RATING              SMALLINT,     -- 1-5
    FEEDBACK_COMMENTS   VARCHAR(1000),
    CREATED_DATE        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE        TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM       VARCHAR(30),
    CONSTRAINT FK_RM_CLIENT_FEEDBACK_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_RM_CLIENT_FEEDBACK_RM_CODE FOREIGN KEY (RM_CODE) REFERENCES RM_MASTER(RM_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_CLIENT_FEEDBACK_CLIENT ON RM_CLIENT_FEEDBACK (APR_CLIENT_CODE);
