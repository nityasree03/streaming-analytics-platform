"""
Tests for dashboard/nl_to_sql.py

Focuses on validate_sql(), the safety-critical function that determines
whether an LLM-generated SQL query is safe to execute. These are pure
unit tests with no external dependencies (no API calls, no database).
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

from nl_to_sql import validate_sql, SQLGenerationError


# --- Valid queries: should pass through unchanged (modulo trailing ;) ---

def test_simple_select_is_valid():
    sql = "SELECT * FROM raw_events"
    assert validate_sql(sql) == sql


def test_select_with_trailing_semicolon_is_stripped():
    sql = "SELECT * FROM raw_events;"
    assert validate_sql(sql) == "SELECT * FROM raw_events"


def test_with_cte_is_valid():
    sql = "WITH foo AS (SELECT 1) SELECT * FROM foo"
    assert validate_sql(sql) == sql


def test_lowercase_select_is_valid():
    sql = "select count(*) from raw_events"
    assert validate_sql(sql) == sql


def test_select_with_leading_whitespace_is_valid():
    sql = "   SELECT * FROM raw_events"
    result = validate_sql(sql)
    assert result.strip().upper().startswith("SELECT")


# --- Invalid queries: must raise SQLGenerationError ---

def test_insert_is_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("INSERT INTO raw_events VALUES (1, 2, 3)")


def test_update_is_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("UPDATE raw_events SET event_type = 'x'")


def test_delete_is_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("DELETE FROM raw_events")


def test_drop_table_is_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("DROP TABLE raw_events")


def test_alter_table_is_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("ALTER TABLE raw_events ADD COLUMN foo TEXT")


def test_truncate_is_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("TRUNCATE raw_events")


def test_query_not_starting_with_select_or_with_is_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("EXPLAIN SELECT * FROM raw_events")


def test_create_table_is_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("CREATE TABLE evil (id INT)")


def test_keyword_in_string_literal_is_still_rejected():
    """
    Defense-in-depth: even if a forbidden keyword appears only inside a
    string literal, our denylist check is conservative and rejects it.
    This may produce false positives (legitimate queries containing the
    word "update" in a string), but for an LLM-generated-SQL safety gate,
    erring toward rejection is the correct tradeoff.
    """
    with pytest.raises(SQLGenerationError):
        validate_sql("SELECT * FROM raw_events WHERE event_type = 'UPDATE'")


def test_select_into_is_handled():
    """
    SELECT ... INTO is a data-modifying form in some SQL dialects
    (creates a new table). Our denylist doesn't explicitly cover "INTO",
    so this test documents current behavior: it is NOT rejected by
    validate_sql(). This is a known limitation -- noted here so it's an
    intentional, visible gap rather than a silent one.
    """
    sql = "SELECT * INTO new_table FROM raw_events"
    # Document current (permissive) behavior rather than assert safety
    # we don't actually provide.
    result = validate_sql(sql)
    assert result == sql
