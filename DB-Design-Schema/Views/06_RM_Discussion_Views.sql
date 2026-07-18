-- =============================================================================
-- FILE:        Views/06_RM_Discussion_Views.sql
-- TAB:         RM Discussion
-- SOURCE TABLES: ../06_RM_Discussion.sql, ../00_Master_Tables.sql
-- SCOPE:       One summary view -- but unlike every other tab's summary view,
--              this one is NOT one row per client. RM Discussion is a
--              list-of-events tab: each discussion session is a distinct
--              qualitative record, so collapsing to one row per client would
--              destroy exactly the narrative content the LLM narration step
--              needs. This view returns one row per discussion session.
--
-- USAGE: views take no parameters; the app queries with a WHERE filter and
-- its own ORDER BY (view row order is not guaranteed by ANSI SQL), e.g.:
--     SELECT * FROM VW_RM_DISCUSSION_SUMMARY
--     WHERE APR_CLIENT_CODE = ? ORDER BY DISCUSSION_DATE DESC
-- =============================================================================

CREATE VIEW VW_RM_DISCUSSION_SUMMARY AS
WITH TOPIC_ROLLUP AS (
    SELECT DISCUSSION_ID, COUNT(*) AS TOPIC_COUNT
    FROM RM_DISCUSSION_TOPIC
    GROUP BY DISCUSSION_ID
),
NEED_ROLLUP AS (
    SELECT DISCUSSION_ID, COUNT(*) AS NEED_COUNT
    FROM RM_CLIENT_NEED_IDENTIFIED
    GROUP BY DISCUSSION_ID
),
SOLUTION_ROLLUP AS (
    SELECT
        DISCUSSION_ID,
        COUNT(*) AS PROPOSED_SOLUTION_COUNT,
        COUNT(CASE WHEN PROPOSAL_STATUS = 'Accepted' THEN 1 END) AS ACCEPTED_SOLUTION_COUNT
    FROM RM_PROPOSED_SOLUTION
    GROUP BY DISCUSSION_ID
),
FOLLOWUP_ROLLUP AS (
    SELECT DISCUSSION_ID, COUNT(*) AS OPEN_FOLLOWUP_ACTION_COUNT
    FROM RM_FOLLOWUP_ACTION
    WHERE ACTION_STATUS = 'Open'
    GROUP BY DISCUSSION_ID
)
SELECT
    DS.DISCUSSION_ID,
    DS.APR_CLIENT_CODE,
    DS.RM_CODE,
    DS.DISCUSSION_DATE,
    DS.DISCUSSION_MODE,
    COALESCE(TR.TOPIC_COUNT, 0)                  AS TOPIC_COUNT,
    COALESCE(NR.NEED_COUNT, 0)                   AS NEED_COUNT,
    COALESCE(SR.PROPOSED_SOLUTION_COUNT, 0)      AS PROPOSED_SOLUTION_COUNT,
    COALESCE(SR.ACCEPTED_SOLUTION_COUNT, 0)      AS ACCEPTED_SOLUTION_COUNT,
    COALESCE(FR.OPEN_FOLLOWUP_ACTION_COUNT, 0)   AS OPEN_FOLLOWUP_ACTION_COUNT,
    OC.OUTCOME_SUMMARY,
    OC.NEXT_STEP,
    OC.NEXT_REVIEW_DATE
FROM RM_DISCUSSION_SESSION DS
LEFT JOIN TOPIC_ROLLUP TR ON TR.DISCUSSION_ID = DS.DISCUSSION_ID
LEFT JOIN NEED_ROLLUP NR ON NR.DISCUSSION_ID = DS.DISCUSSION_ID
LEFT JOIN SOLUTION_ROLLUP SR ON SR.DISCUSSION_ID = DS.DISCUSSION_ID
LEFT JOIN FOLLOWUP_ROLLUP FR ON FR.DISCUSSION_ID = DS.DISCUSSION_ID
LEFT JOIN RM_DISCUSSION_OUTCOME OC ON OC.DISCUSSION_ID = DS.DISCUSSION_ID;
