# Real-Time Streaming Analytics Platform

> A production-style, real-time analytics pipeline for a SaaS company — tracking user signups, logins, feature usage, and upgrades in real time using Kafka, Spark Structured Streaming, PostgreSQL, and Streamlit.

## Status
🚧 Under active development — built in public, phase by phase.

## Architecture
Kafka Producer → Kafka → Spark Structured Streaming → PostgreSQL → Streamlit Dashboard → Grafana Monitoring

## Tech Stack
Python · Apache Kafka · Apache Spark (Structured Streaming) · PostgreSQL · Streamlit · Docker · Grafana

## Project Structure
- `producer/` — Kafka event producer (synthetic SaaS user events via Faker)
- `spark/` — Spark Structured Streaming jobs for real-time KPI computation
- `dashboard/` — Streamlit executive dashboard
- `database/` — PostgreSQL schema and SQL analytics
- `monitoring/` — Grafana dashboards for pipeline observability
- `tests/` — Unit, integration, and data validation tests
- `docs/` — Architecture diagrams, deployment guide, interview prep
- `architecture/` — System design diagrams
- `scripts/` — Setup/automation scripts

## Setup
_Instructions coming in later phases._

## License
MIT
