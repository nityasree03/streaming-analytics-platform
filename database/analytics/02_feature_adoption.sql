-- ===========================================================================
-- Feature Adoption
-- ===========================================================================
-- Business value:
--   Identifies which product features are most/least used, and how usage
--   varies by subscription tier. Product teams use this to prioritize
--   roadmap investment and to find features that could justify upsell
--   campaigns (e.g. "free users barely touch X -- could X drive upgrades?").
--
-- Interview value:
--   Combines COUNT with window functions / subqueries to compute
--   "percentage of total" -- a very common analyst SQL pattern.
-- ===========================================================================

-- Overall feature usage counts, ranked
SELECT
    feature_name,
    COUNT(*) AS usage_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2
    ) AS pct_of_all_feature_events
FROM raw_events
WHERE event_type = 'feature_used'
  AND feature_name IS NOT NULL
GROUP BY feature_name
ORDER BY usage_count DESC;


-- Feature usage broken down by plan tier (which tiers use which features most)
SELECT
    plan_tier,
    feature_name,
    COUNT(*) AS usage_count
FROM raw_events
WHERE event_type = 'feature_used'
  AND feature_name IS NOT NULL
GROUP BY plan_tier, feature_name
ORDER BY plan_tier, usage_count DESC;


-- Distinct users who have used each feature at least once
-- (adoption breadth, not just raw event volume)
SELECT
    feature_name,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(*) AS total_uses,
    ROUND(COUNT(*)::numeric / COUNT(DISTINCT user_id), 2) AS avg_uses_per_user
FROM raw_events
WHERE event_type = 'feature_used'
  AND feature_name IS NOT NULL
GROUP BY feature_name
ORDER BY unique_users DESC;
