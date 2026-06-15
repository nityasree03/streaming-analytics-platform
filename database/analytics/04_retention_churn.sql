-- ===========================================================================
-- Retention & Churn Signals
-- ===========================================================================
-- Business value:
--   Identifies users at risk of churning (no recent activity) so customer
--   success / marketing teams can intervene with re-engagement campaigns
--   before the user is fully lost.
--
-- Interview value:
--   Combines MAX(timestamp) per user with date-arithmetic bucketing --
--   a foundational pattern for retention curves and recency segmentation
--   (similar to RFM analysis).
-- ===========================================================================

-- Per-user last activity timestamp and "days since last seen"
-- (relative to the most recent event in the dataset, since this is
-- historical/snapshot data rather than live "now")
WITH dataset_now AS (
    SELECT MAX(event_timestamp) AS ts FROM raw_events
),
last_seen AS (
    SELECT
        user_id,
        MAX(event_timestamp) AS last_event_at
    FROM raw_events
    GROUP BY user_id
)
SELECT
    last_seen.user_id,
    last_seen.last_event_at,
    EXTRACT(EPOCH FROM (dataset_now.ts - last_seen.last_event_at)) / 60 AS minutes_since_last_seen
FROM last_seen, dataset_now
ORDER BY minutes_since_last_seen DESC
LIMIT 20;


-- Recency segmentation: bucket users by how long since their last event
-- (using minute-based buckets since our dataset spans hours, not months;
-- in production with longer history this would use day/week buckets)
WITH dataset_now AS (
    SELECT MAX(event_timestamp) AS ts FROM raw_events
),
last_seen AS (
    SELECT
        user_id,
        MAX(event_timestamp) AS last_event_at
    FROM raw_events
    GROUP BY user_id
)
SELECT
    CASE
        WHEN EXTRACT(EPOCH FROM (dataset_now.ts - last_seen.last_event_at)) / 60 < 30 THEN 'active (< 30 min)'
        WHEN EXTRACT(EPOCH FROM (dataset_now.ts - last_seen.last_event_at)) / 60 < 120 THEN 'cooling (30-120 min)'
        ELSE 'churned (> 120 min)'
    END AS recency_segment,
    COUNT(*) AS user_count
FROM last_seen, dataset_now
GROUP BY recency_segment
ORDER BY user_count DESC;


-- Users whose most recent event was 'logout' with no subsequent activity
-- -- a simple heuristic "session ended and didn't return" signal.
WITH last_event_per_user AS (
    SELECT DISTINCT ON (user_id)
        user_id,
        event_type,
        event_timestamp
    FROM raw_events
    ORDER BY user_id, event_timestamp DESC
)
SELECT
    COUNT(*) AS users_whose_last_action_was_logout
FROM last_event_per_user
WHERE event_type = 'logout';

-- ===========================================================================
-- DATA NOTE: All 500 users fall into "active (< 30 min)" because this
-- dataset is a live, continuous stream spanning only minutes/hours, not
-- the days/weeks needed to observe real churn. In production, this query
-- would be run against historical data spanning weeks/months, where the
-- "cooling" and "churned" buckets would contain meaningful user counts.
-- The bucket thresholds (30 min / 120 min) would also be changed to
-- day-based thresholds (e.g. 7 days / 30 days) for a real product.
-- ===========================================================================
