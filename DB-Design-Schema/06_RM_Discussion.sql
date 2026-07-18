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
    DISCUSSION_ID     BIGINT       NOT NULL PRIMARY KEY,
    APR_CLIENT_CODE   VARCHAR(14)  NOT NULL REFERENCES CLIENT_MASTER(APR_CLIENT_CODE),
    RM_CODE           VARCHAR(7)   NOT NULL REFERENCES RM_MASTER(RM_CODE),
    MEETING_ID        BIGINT       REFERENCES CMS_MEETING_RECORD(MEETING_ID),  -- see 01_CMS.sql, nullable
    DISCUSSION_DATE   DATE         NOT NULL,
    DISCUSSION_MODE   VARCHAR(20),  -- In-Person / Virtual / Telephonic
    CREATED_DATE      TIMESTAMP    NOT NULL,
    UPDATED_DATE      TIMESTAMP,
    SOURCE_SYSTEM     VARCHAR(30)
);

CREATE INDEX IX_RM_DISCUSSION_SESSION_CLIENT ON RM_DISCUSSION_SESSION (APR_CLIENT_CODE);


-- -----------------------------------------------------------------------------
-- RM_DISCUSSION_TOPIC: topics covered within a discussion session.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_DISCUSSION_TOPIC (
    TOPIC_ID             BIGINT       NOT NULL PRIMARY KEY,
    DISCUSSION_ID        BIGINT       NOT NULL REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID),
    TOPIC_CATEGORY       VARCHAR(50),
    TOPIC_DESCRIPTION    VARCHAR(500),
    CREATED_DATE         TIMESTAMP    NOT NULL,
    UPDATED_DATE         TIMESTAMP,
    SOURCE_SYSTEM        VARCHAR(30)
);

CREATE INDEX IX_RM_DISCUSSION_TOPIC_DISCUSSION ON RM_DISCUSSION_TOPIC (DISCUSSION_ID);


-- -----------------------------------------------------------------------------
-- RM_CLIENT_NEED_IDENTIFIED: client needs surfaced during a discussion.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_CLIENT_NEED_IDENTIFIED (
    NEED_ID             BIGINT       NOT NULL PRIMARY KEY,
    DISCUSSION_ID       BIGINT       NOT NULL REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID),
    NEED_CATEGORY       VARCHAR(50),
    NEED_DESCRIPTION    VARCHAR(500),
    PRIORITY            VARCHAR(10),  -- High / Medium / Low
    CREATED_DATE        TIMESTAMP    NOT NULL,
    UPDATED_DATE        TIMESTAMP,
    SOURCE_SYSTEM       VARCHAR(30)
);

CREATE INDEX IX_RM_CLIENT_NEED_IDENTIFIED_DISCUSSION ON RM_CLIENT_NEED_IDENTIFIED (DISCUSSION_ID);


-- -----------------------------------------------------------------------------
-- RM_PROPOSED_SOLUTION: bank products/solutions proposed against an
-- identified need.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_PROPOSED_SOLUTION (
    SOLUTION_ID             BIGINT       NOT NULL PRIMARY KEY,
    DISCUSSION_ID           BIGINT       NOT NULL REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID),
    NEED_ID                 BIGINT       REFERENCES RM_CLIENT_NEED_IDENTIFIED(NEED_ID),
    PROPOSED_PRODUCT_CODE   VARCHAR(10)  REFERENCES PRODUCT_MASTER(PRODUCT_CODE),
    PROPOSED_VALUE          NUMERIC(18,2),
    PROPOSAL_STATUS         VARCHAR(20),  -- Proposed / Accepted / Declined / UnderReview
    CREATED_DATE            TIMESTAMP    NOT NULL,
    UPDATED_DATE            TIMESTAMP,
    SOURCE_SYSTEM           VARCHAR(30)
);

CREATE INDEX IX_RM_PROPOSED_SOLUTION_DISCUSSION ON RM_PROPOSED_SOLUTION (DISCUSSION_ID);


-- -----------------------------------------------------------------------------
-- RM_FOLLOWUP_ACTION: agreed follow-up actions and their owners/status.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_FOLLOWUP_ACTION (
    ACTION_ID             BIGINT       NOT NULL PRIMARY KEY,
    DISCUSSION_ID         BIGINT       NOT NULL REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID),
    ACTION_DESCRIPTION    VARCHAR(500),
    OWNER_RM_CODE         VARCHAR(7)   REFERENCES RM_MASTER(RM_CODE),
    DUE_DATE              DATE,
    ACTION_STATUS         VARCHAR(20),  -- Open / Completed / Overdue
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_RM_FOLLOWUP_ACTION_DISCUSSION ON RM_FOLLOWUP_ACTION (DISCUSSION_ID);


-- -----------------------------------------------------------------------------
-- RM_DISCUSSION_OUTCOME: closing summary and next-step for a discussion.
-- -----------------------------------------------------------------------------
CREATE TABLE RM_DISCUSSION_OUTCOME (
    OUTCOME_ID           BIGINT       NOT NULL PRIMARY KEY,
    DISCUSSION_ID        BIGINT       NOT NULL REFERENCES RM_DISCUSSION_SESSION(DISCUSSION_ID),
    OUTCOME_SUMMARY       VARCHAR(1000),
    NEXT_STEP             VARCHAR(500),
    NEXT_REVIEW_DATE      DATE,
    CREATED_DATE          TIMESTAMP    NOT NULL,
    UPDATED_DATE          TIMESTAMP,
    SOURCE_SYSTEM         VARCHAR(30)
);

CREATE INDEX IX_RM_DISCUSSION_OUTCOME_DISCUSSION ON RM_DISCUSSION_OUTCOME (DISCUSSION_ID);
