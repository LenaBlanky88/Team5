-- ============================================================
-- queries.sql — 5 analytical queries for Customer Journey Forensics
-- Run against customer_journey_forensics.db
-- ============================================================


-- ------------------------------------------------------------
-- Query 1: Escalation Rate by Channel
-- Which channels most frequently produce escalated interactions?
-- Useful for identifying channel-level failure hotspots.
-- ------------------------------------------------------------
SELECT
    ch.channel_name,
    ch.media_type,
    COUNT(*)                                                    AS total_interactions,
    SUM(i.escalation_flag)                                      AS escalations,
    ROUND(100.0 * SUM(i.escalation_flag) / COUNT(*), 1)        AS escalation_rate_pct,
    ROUND(AVG(i.csat), 2)                                       AS avg_csat
FROM interactions i
JOIN channels ch ON i.channel_id = ch.channel_id
GROUP BY ch.channel_name, ch.media_type
ORDER BY escalation_rate_pct DESC;


-- ------------------------------------------------------------
-- Query 2: Average Resolution Time by Industry and Case Type
-- How long (in days) does it take to close a journey session,
-- broken down by industry and the type of case.
-- ------------------------------------------------------------
SELECT
    js.industry,
    js.case_type,
    COUNT(*)                                                                    AS total_sessions,
    ROUND(AVG(
        JULIANDAY(js.last_contact_time) - JULIANDAY(js.first_contact_time)
    ), 1)                                                                       AS avg_days_to_close,
    MAX(
        JULIANDAY(js.last_contact_time) - JULIANDAY(js.first_contact_time)
    )                                                                           AS max_days_to_close,
    ROUND(AVG(js.risk_score), 2)                                                AS avg_risk_score
FROM journey_sessions js
WHERE js.first_contact_time IS NOT NULL
  AND js.last_contact_time  IS NOT NULL
GROUP BY js.industry, js.case_type
ORDER BY avg_days_to_close DESC;


-- ------------------------------------------------------------
-- Query 3: Repeat Contact Rate — Journeys with 4+ Interactions
-- Identifies sessions where customers had to contact support
-- four or more times before resolution — a key churn signal.
-- ------------------------------------------------------------
SELECT
    js.industry,
    js.scenario_title,
    js.master_contact_id,
    c.customer_name,
    js.total_interactions,
    js.risk_score,
    js.risk_label,
    js.session_status,
    -- Count distinct channels used (channel switching indicator)
    (
        SELECT COUNT(DISTINCT i2.channel_id)
        FROM interactions i2
        WHERE i2.master_contact_id = js.master_contact_id
          AND i2.channel_id IS NOT NULL
    )                                                           AS distinct_channels_used,
    -- Sentiment at final interaction
    (
        SELECT i3.overall_sentiment
        FROM interactions i3
        WHERE i3.master_contact_id = js.master_contact_id
        ORDER BY i3.interaction_sequence DESC
        LIMIT 1
    )                                                           AS final_sentiment
FROM journey_sessions js
JOIN customers c ON js.customer_id = c.customer_id
WHERE js.total_interactions >= 4
ORDER BY js.total_interactions DESC, js.risk_score DESC;


-- ------------------------------------------------------------
-- Query 4: Broken Promise Pattern — Top Failure Pattern Types
-- Ranks failure patterns by frequency across all journeys.
-- Surfaces the most systemic CX breakdown categories.
-- ------------------------------------------------------------
SELECT
    fp.pattern_type,
    fp.severity,
    COUNT(*)                                                    AS occurrences,
    COUNT(DISTINCT fp.master_contact_id)                        AS journeys_affected,
    -- Which industries see this pattern?
    GROUP_CONCAT(DISTINCT js.industry)                          AS industries,
    ROUND(AVG(js.risk_score), 2)                                AS avg_risk_score_in_affected_journeys
FROM failure_patterns fp
JOIN journey_sessions js ON fp.master_contact_id = js.master_contact_id
GROUP BY fp.pattern_type, fp.severity
ORDER BY occurrences DESC, fp.severity DESC;


-- ------------------------------------------------------------
-- Query 5: Agent Performance — Sentiment and CSAT by Agent
-- For human agents with 2+ interactions, shows average CSAT,
-- sentiment distribution, and escalation rate.
-- Helps identify agents who consistently handle escalations
-- vs agents generating them.
-- ------------------------------------------------------------
SELECT
    a.agent_id,
    a.agent_name,
    a.team_name,
    COUNT(i.contact_id)                                         AS total_interactions,
    ROUND(AVG(i.csat), 2)                                       AS avg_csat,
    SUM(CASE WHEN i.overall_sentiment = 'Very Negative' THEN 1 ELSE 0 END)  AS very_negative_count,
    SUM(CASE WHEN i.overall_sentiment = 'Positive'      THEN 1 ELSE 0 END)  AS positive_count,
    SUM(i.escalation_flag)                                      AS escalations_generated,
    SUM(i.transfer_flag)                                        AS transfers_made,
    ROUND(AVG(i.duration_seconds) / 60.0, 1)                   AS avg_call_duration_mins
FROM interactions i
JOIN agents a ON i.agent_id = a.agent_id
WHERE a.agent_type = 'Human'
GROUP BY a.agent_id, a.agent_name, a.team_name
HAVING total_interactions >= 2
ORDER BY avg_csat ASC NULLS LAST, escalations_generated DESC;
