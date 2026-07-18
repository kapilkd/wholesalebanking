-- =============================================================================
-- MariaDB/MySQL deployment copy, generated from ../06_RM_Discussion.sql for the local
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
-- The design source (../06_RM_Discussion.sql) remains the source of truth for schema
-- design; this file is a build artifact of it, not hand-maintained.
-- =============================================================================

-- =============================================================================
-- FILE:        06_RM_Discussion.sql
-- TAB:         RM Discussion
-- SCOPE:       The structured content of a specific RM-client discussion:
--              topics covered, needs identified, solutions proposed, agreed
--              follow-up actions, and outcomes. Distinct from CMS_MEETING_RECORD
--              (01_CMS.sql), which is the general meeting log entry (date,
--              location, attendees) -- a discussion session here may
--              optionally link back to the meeting it was logged under.
-- OWNS:        RM_DISCUSSION_SESSION, RM_DISCUSSION_TOPIC,
--              RM_CLIENT_NEED_IDENTIFIED, RM_PROPOSED_SOLUTION,
--              RM_FOLLOWUP_ACTION, RM_DISCUSSION_OUTCOME
-- REFERENCES:  CLIENT_MASTER, RM_MASTER, PRODUCT_MASTER
--              (see 00_Master_Tables.sql) -- not redefined here.
--              CMS_MEETING_RECORD (see 01_CMS.sql) -- optional FK link.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- RM_DISCUSSION_SESSION: header record for one discussion session with a
-- client. MEETING_ID is nullable -- only set when the discussion was logged
-- against a formal meeting record in CMS.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_DISCUSSION_SESSION (
    DISCUSSION_ID     BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL,
    RM_CODE           VARCHAR(7)   NOT NULL,
    MEETING_ID        BIGINT,  -- see 01_CMS.sql, nullable
    DISCUSSION_DATE   DATE         NOT NULL,
    DISCUSSION_MODE   VARCHAR(20),  -- In-Person / Virtual / Telephonic
    CREATED_DATE      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE      TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM     VARCHAR(30),
    CONSTRAINT FK_RM_DISCUSSION_SESSION_APR_CLIENT_CODE FOREIGN KEY (APR_CLIENT_CODE) REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    CONSTRAINT FK_RM_DISCUSSION_SESSION_RM_CODE FOREIGN KEY (RM_CODE) REFERENCES RM_MASTER(RM_CODE),
    CONSTRAINT FK_RM_DISCUSSION_SESSION_MEETING_ID FOREIGN KEY (MEETING_ID) REFERENCES CMS_MEETING_RECORD(MEETING_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_DISCUSSION_SESSION_CLIENT ON RM_DISCUSSION_SESSION (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_DISCUSSION_TOPIC: topics covered within a discussion session.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_DISCUSSION_TOPIC (
    TOPIC_ID             BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    DISCUSSION_ID        BIGINT       NOT NULL,
    TOPIC_CATEGORY       VARCHAR(50),
    TOPIC_DESCRIPTION    VARCHAR(500),
    CREATED_DATE         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE         TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM        VARCHAR(30),
    CONSTRAINT FK_RM_DISCUSSION_TOPIC_DISCUSSION_ID FOREIGN KEY (DISCUSSION_ID) REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_DISCUSSION_TOPIC_DISCUSSION ON RM_DISCUSSION_TOPIC (DISCUSSION_ID);


-- -----------------------------------------------------------------------------
-- RM_CLIENT_NEED_IDENTIFIED: client needs surfaced during a discussion.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_CLIENT_NEED_IDENTIFIED (
    NEED_ID             BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    DISCUSSION_ID       BIGINT       NOT NULL,
    NEED_CATEGORY       VARCHAR(50),
    NEED_DESCRIPTION    VARCHAR(500),
    PRIORITY            VARCHAR(10),  -- High / Medium / Low
    CREATED_DATE        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE        TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM       VARCHAR(30),
    CONSTRAINT FK_RM_CLIENT_NEED_IDENTIFIED_DISCUSSION_ID FOREIGN KEY (DISCUSSION_ID) REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_CLIENT_NEED_IDENTIFIED_DISCUSSION ON RM_CLIENT_NEED_IDENTIFIED (DISCUSSION_ID);


-- -----------------------------------------------------------------------------
-- RM_PROPOSED_SOLUTION: bank products/solutions proposed against an
-- identified need.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_PROPOSED_SOLUTION (
    SOLUTION_ID             BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    DISCUSSION_ID           BIGINT       NOT NULL,
    NEED_ID                 BIGINT,
    PROPOSED_PRODUCT_CODE   VARCHAR(10),
    PROPOSED_VALUE          NUMERIC(18,2),
    PROPOSAL_STATUS         VARCHAR(20),  -- Proposed / Accepted / Declined / UnderReview
    CREATED_DATE            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE            TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM           VARCHAR(30),
    CONSTRAINT FK_RM_PROPOSED_SOLUTION_DISCUSSION_ID FOREIGN KEY (DISCUSSION_ID) REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID),
    CONSTRAINT FK_RM_PROPOSED_SOLUTION_NEED_ID FOREIGN KEY (NEED_ID) REFERENCES RM_CLIENT_NEED_IDENTIFIED(NEED_ID),
    CONSTRAINT FK_RM_PROPOSED_SOLUTION_PROPOSED_PRODUCT_CODE FOREIGN KEY (PROPOSED_PRODUCT_CODE) REFERENCES PRODUCT_MASTER(PRODUCT_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_PROPOSED_SOLUTION_DISCUSSION ON RM_PROPOSED_SOLUTION (DISCUSSION_ID);


-- -----------------------------------------------------------------------------
-- RM_FOLLOWUP_ACTION: agreed follow-up actions and their owners/status.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_FOLLOWUP_ACTION (
    ACTION_ID             BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    DISCUSSION_ID         BIGINT       NOT NULL,
    ACTION_DESCRIPTION    VARCHAR(500),
    OWNER_RM_CODE         VARCHAR(7),
    DUE_DATE              DATE,
    ACTION_STATUS         VARCHAR(20),  -- Open / Completed / Overdue
    CREATED_DATE          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE          TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM         VARCHAR(30),
    CONSTRAINT FK_RM_FOLLOWUP_ACTION_DISCUSSION_ID FOREIGN KEY (DISCUSSION_ID) REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID),
    CONSTRAINT FK_RM_FOLLOWUP_ACTION_OWNER_RM_CODE FOREIGN KEY (OWNER_RM_CODE) REFERENCES RM_MASTER(RM_CODE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_FOLLOWUP_ACTION_DISCUSSION ON RM_FOLLOWUP_ACTION (DISCUSSION_ID);


-- -----------------------------------------------------------------------------
-- RM_DISCUSSION_OUTCOME: closing summary and next-step for a discussion.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_DISCUSSION_OUTCOME (
    OUTCOME_ID           BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    DISCUSSION_ID        BIGINT       NOT NULL,
    OUTCOME_SUMMARY       VARCHAR(1000),
    NEXT_STEP             VARCHAR(500),
    NEXT_REVIEW_DATE      DATE,
    CREATED_DATE          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_DATE          TIMESTAMP NULL DEFAULT NULL,
    SOURCE_SYSTEM         VARCHAR(30),
    CONSTRAINT FK_RM_DISCUSSION_OUTCOME_DISCUSSION_ID FOREIGN KEY (DISCUSSION_ID) REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX IX_RM_DISCUSSION_OUTCOME_DISCUSSION ON RM_DISCUSSION_OUTCOME (DISCUSSION_ID);
