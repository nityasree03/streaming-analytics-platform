# Grafana Monitoring

## Overview
Grafana provides operational/infrastructure monitoring for the streaming
pipeline, complementing the Streamlit dashboard's business-metrics view.

- **Streamlit dashboard** (Phase 8): "What is happening in the product?"
  (events per minute, business KPIs)
- **Grafana dashboard** (this phase): "Is the pipeline itself healthy?"
  (data freshness, throughput trends)

## Access
- URL: http://localhost:3000
- Default credentials: admin / admin (change for any non-local deployment)

## Data Source
- Type: PostgreSQL
- Host: `postgres:5432` (Docker service name -- internal network)
- Database: `streaming_analytics`

## Dashboard: Pipeline Health Monitor

### Panel 1 - Seconds Since Last Pipeline Update
```sql
SELECT
  EXTRACT(EPOCH FROM (now() - MAX(created_at))) AS value
FROM aggregated_metrics
```
A "heartbeat" metric: how long since Spark last wrote a row. In production,
this would back an alert (e.g. PagerDuty/Slack) if it exceeds a threshold
(e.g. 120 seconds), indicating the streaming job has stalled or crashed.

### Panel 2 - Events Per Minute (Pipeline Throughput)
```sql
SELECT
  window_start AS time,
  metric_value AS "Events Per Minute"
FROM aggregated_metrics
WHERE metric_name = 'events_per_minute'
ORDER BY window_start
```
Time-series view of ingestion throughput over time -- useful for spotting
traffic anomalies (sudden drops/spikes) at the infrastructure level.

## Future Work (Not Implemented)
A production setup would add dedicated exporters for deeper observability:
- **Kafka**: JMX exporter for consumer lag, broker throughput, partition health
- **Spark**: Spark's built-in metrics sink (Prometheus format) for job/stage/executor metrics
- **Container-level**: cAdvisor or Docker stats exporter for CPU/memory per service

These were scoped out of this build to focus on the core data pipeline,
but represent the natural "next steps" for a production-grade deployment.
