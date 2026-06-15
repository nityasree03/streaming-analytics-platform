"""
Integration tests for database/analytics/*.sql

These tests connect to the live PostgreSQL database (as configured for
local development) and verify that each analytics query executes without
error and returns a non-empty, well-shaped result.

Unlike tests/test_event_generator.py and tests/test_nl_to_sql.py, these
are integration tests requiring a running streaming-postgres container
with data in raw_events/aggregated_metrics. If the database is
unreachable, all tests in this module are skipped rather than failed.
"""

import os

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

PG_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "streaming_analytics",
    "user": "streaming_user",
    "password": "streaming_pass",
}

ANALYTICS_DIR = os.path.join(os.path.dirname(__file__), "..", "database", "analytics")


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        f"postgresql+psycopg2://{PG_CONFIG['user']}:{PG_CONFIG['password']}"
        f"@{PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']}"
    )
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"Database not reachable, skipping integration tests: {e}")
    return eng


def split_statements(sql_text):
    lines = [
        line for line in sql_text.splitlines()
        if not line.strip().startswith("--")
    ]
    cleaned = "\n".join(lines)
    statements = [s.strip() for s in cleaned.split(";")]
    return [s for s in statements if s]


@pytest.fixture(scope="module")
def raw_events_has_data(engine):
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM raw_events")).scalar()
    if count == 0:
        pytest.skip("raw_events table is empty, skipping analytics query tests")
    return count


@pytest.mark.parametrize("filename", [
    "01_dau_wau_mau.sql",
    "02_feature_adoption.sql",
    "03_conversion_funnel.sql",
    "04_retention_churn.sql",
])
def test_analytics_query_executes_without_error(engine, raw_events_has_data, filename):
    filepath = os.path.join(ANALYTICS_DIR, filename)
    with open(filepath) as f:
        sql_text = f.read()

    statements = split_statements(sql_text)
    assert len(statements) > 0, filename + " contains no executable statements"

    for statement in statements:
        df = pd.read_sql(statement, engine)
        assert len(df) > 0, "Statement in " + filename + " returned no rows"


def test_dau_wau_mau_ratio_is_between_zero_and_one(engine, raw_events_has_data):
    filepath = os.path.join(ANALYTICS_DIR, "01_dau_wau_mau.sql")
    with open(filepath) as f:
        sql_text = f.read()

    statements = split_statements(sql_text)
    ratio_query = statements[-1]
    df = pd.read_sql(ratio_query, engine)

    assert "dau_mau_ratio" in df.columns
    ratio = df["dau_mau_ratio"].iloc[0]
    assert 0 <= ratio <= 1
