-- =====================================================================
-- schema.sql
--
-- PostgreSQL schema for the Real-Time Streaming Analytics Platform.
-- Stores raw SaaS user events and the aggregated KPIs computed by the
-- Spark Structured Streaming pipeline.
-- =====================================================================

-- ---------------------------------------------------------------------
-- raw_events
--
-- Full-fidelity copy of every event ingested from Kafka. Useful for
-- replaying/debugging the pipeline and for ad-hoc SQL analysis that
-- the streaming aggregations don't cover.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_events (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    session_id      VARCHAR(36) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_type      VARCHAR(50) NOT NULL,
    plan_tier       VARCHAR(20) NOT NULL,
    feature_name    VARCHAR(100),
    country         VARCHAR(10),
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for time-range queries (e.g. "events in the last hour")
CREATE INDEX IF NOT EXISTS idx_raw_events_timestamp
    ON raw_events (event_timestamp);

-- Index for per-user lookups (e.g. "all events for user X")
CREATE INDEX IF NOT EXISTS idx_raw_events_user_id
    ON raw_events (user_id);

-- Index for filtering by event type (e.g. "all purchase events")
CREATE INDEX IF NOT EXISTS idx_raw_events_event_type
    ON raw_events (event_type);


-- ---------------------------------------------------------------------
-- user_metrics
--
-- Per-user rollup. One row per user, updated as new events arrive.
-- Powers user-level views: last activity, plan tier, lifetime event count.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_metrics (
    user_id           UUID PRIMARY KEY,
    plan_tier         VARCHAR(20) NOT NULL,
    country           VARCHAR(10),
    total_events      BIGINT NOT NULL DEFAULT 0,
    first_seen        TIMESTAMPTZ NOT NULL,
    last_seen         TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for "active users in the last N days" type queries
CREATE INDEX IF NOT EXISTS idx_user_metrics_last_seen
    ON user_metrics (last_seen);

-- Index for segmenting users by plan (e.g. free vs paid breakdown)
CREATE INDEX IF NOT EXISTS idx_user_metrics_plan_tier
    ON user_metrics (plan_tier);


-- ---------------------------------------------------------------------
-- aggregated_metrics
--
-- Time-windowed KPI values produced by the Spark Structured Streaming
-- job (e.g. events per minute, active users per window). This is the
-- primary table the Streamlit dashboard reads from for time-series charts.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aggregated_metrics (
    id            BIGSERIAL PRIMARY KEY,
    window_start  TIMESTAMPTZ NOT NULL,
    window_end    TIMESTAMPTZ NOT NULL,
    metric_name   VARCHAR(100) NOT NULL,
    metric_value  DOUBLE PRECISION NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Prevent duplicate writes for the same metric/window combination
    -- (Spark may reprocess a window before its watermark closes it).
    UNIQUE (window_start, window_end, metric_name)
);

-- Index for time-series queries ("show me event_count over the last hour")
CREATE INDEX IF NOT EXISTS idx_aggregated_metrics_window
    ON aggregated_metrics (window_start, metric_name);


-- ---------------------------------------------------------------------
-- feature_usage
--
-- Per-feature, per-time-window usage counts. Powers the Feature
-- Adoption dashboard page (Phase 8) and feature adoption SQL (Phase 10).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feature_usage (
    id            BIGSERIAL PRIMARY KEY,
    window_start  TIMESTAMPTZ NOT NULL,
    window_end    TIMESTAMPTZ NOT NULL,
    feature_name  VARCHAR(100) NOT NULL,
    usage_count   BIGINT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (window_start, window_end, feature_name)
);

-- Index for "most-used features over time" queries
CREATE INDEX IF NOT EXISTS idx_feature_usage_window
    ON feature_usage (window_start, feature_name);
