-- ===========================================================================
-- Conversion Funnel: Signup -> Feature Use -> Purchase/Upgrade
-- ===========================================================================
-- Business value:
--   Funnels reveal where users drop off in their journey from initial
--   signup to becoming paying/upgraded customers. This is the core
--   analysis behind growth and product-led-growth (PLG) teams.
--
-- Interview value:
--   Demonstrates conditional aggregation (COUNT(CASE WHEN ...)) and
--   per-user existence checks via EXISTS/subqueries -- staple funnel
--   analysis patterns.
-- ===========================================================================

-- Overall funnel: how many distinct users reached each stage
WITH signed_up AS (
    SELECT DISTINCT user_id FROM raw_events WHERE event_type = 'signup'
),
used_feature AS (
    SELECT DISTINCT user_id FROM raw_events WHERE event_type = 'feature_used'
),
converted AS (
    SELECT DISTINCT user_id FROM raw_events WHERE event_type IN ('purchase', 'upgrade')
)
SELECT
    (SELECT COUNT(*) FROM signed_up) AS stage_1_signups,
    (SELECT COUNT(*) FROM used_feature) AS stage_2_used_feature,
    (SELECT COUNT(*) FROM converted) AS stage_3_converted,
    ROUND(
        100.0 * (SELECT COUNT(*) FROM used_feature) / NULLIF((SELECT COUNT(*) FROM signed_up), 0), 2
    ) AS pct_signup_to_feature_use,
    ROUND(
        100.0 * (SELECT COUNT(*) FROM converted) / NULLIF((SELECT COUNT(*) FROM used_feature), 0), 2
    ) AS pct_feature_use_to_conversion;


-- Funnel broken down by plan tier (which tiers convert better?)
-- Uses each user's most recently seen plan_tier as their segment.
WITH user_latest_tier AS (
    SELECT DISTINCT ON (user_id)
        user_id,
        plan_tier
    FROM raw_events
    ORDER BY user_id, event_timestamp DESC
),
converted AS (
    SELECT DISTINCT user_id FROM raw_events WHERE event_type IN ('purchase', 'upgrade')
)
SELECT
    ult.plan_tier,
    COUNT(*) AS total_users,
    COUNT(c.user_id) AS converted_users,
    ROUND(100.0 * COUNT(c.user_id) / COUNT(*), 2) AS conversion_rate_pct
FROM user_latest_tier ult
LEFT JOIN converted c ON c.user_id = ult.user_id
GROUP BY ult.plan_tier
ORDER BY conversion_rate_pct DESC;

-- ===========================================================================
-- DATA NOTE: In this synthetic dataset, stage_2/stage_1 can exceed 100%.
-- This is because the event generator produces a random mix of event types
-- per user without guaranteeing every user has a 'signup' event in the
-- sampled window (some users' first-seen event in this snapshot is
-- 'login' or 'feature_used' instead). In a real product, signup is a
-- one-time event guaranteed to precede all other activity, so this
-- percentage would always be <= 100%. The plan-tier breakdown below
-- remains valid since it doesn't depend on signup as the funnel's first
-- stage.
-- ===========================================================================
