-- ===========================================================================
-- DAU / WAU / MAU (Daily / Weekly / Monthly Active Users)
-- ===========================================================================
-- Business value:
--   These are the foundational engagement metrics for any SaaS product.
--   DAU/MAU ("stickiness ratio") indicates how habitual product usage is --
--   a ratio near 1 means users return almost daily; a ratio near 0
--   suggests sporadic, infrequent engagement.
--
-- Interview value:
--   "How would you calculate DAU from an events table?" is a near-universal
--   SQL screening question for analyst roles. The key insight is COUNT(DISTINCT)
--   on user_id, grouped by a truncated date.
-- ===========================================================================

-- Daily Active Users: distinct users per calendar day
SELECT
    DATE(event_timestamp) AS activity_date,
    COUNT(DISTINCT user_id) AS dau
FROM raw_events
GROUP BY DATE(event_timestamp)
ORDER BY activity_date;


-- Weekly Active Users: distinct users per ISO week
SELECT
    DATE_TRUNC('week', event_timestamp) AS week_start,
    COUNT(DISTINCT user_id) AS wau
FROM raw_events
GROUP BY DATE_TRUNC('week', event_timestamp)
ORDER BY week_start;


-- Monthly Active Users: distinct users per calendar month
SELECT
    DATE_TRUNC('month', event_timestamp) AS month_start,
    COUNT(DISTINCT user_id) AS mau
FROM raw_events
GROUP BY DATE_TRUNC('month', event_timestamp)
ORDER BY month_start;


-- DAU / MAU "stickiness" ratio for the most recent day with data,
-- compared against the MAU for that day's month.
WITH latest_day AS (
    SELECT MAX(DATE(event_timestamp)) AS d FROM raw_events
),
dau AS (
    SELECT COUNT(DISTINCT user_id) AS dau_count
    FROM raw_events, latest_day
    WHERE DATE(event_timestamp) = latest_day.d
),
mau AS (
    SELECT COUNT(DISTINCT user_id) AS mau_count
    FROM raw_events, latest_day
    WHERE DATE_TRUNC('month', event_timestamp) = DATE_TRUNC('month', latest_day.d)
)
SELECT
    dau.dau_count,
    mau.mau_count,
    ROUND(dau.dau_count::numeric / mau.mau_count, 3) AS dau_mau_ratio
FROM dau, mau;
