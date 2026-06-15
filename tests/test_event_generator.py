"""
Tests for producer/event_generator.py

Verifies that generate_event() produces well-formed events matching the
expected schema: correct keys, valid enum values for categorical fields,
correct conditional logic (feature_name only populated for feature_used
events), and valid UUID/ISO-timestamp formats.
"""

import sys
import os
import uuid
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "producer"))

from event_generator import (
    generate_event,
    EVENT_TYPES,
    PLAN_TIERS,
    FEATURE_NAMES,
    COUNTRIES,
    USER_POOL,
)


def test_generate_event_has_expected_keys():
    event = generate_event()
    expected_keys = {
        "user_id", "session_id", "timestamp", "event_type",
        "plan_tier", "feature_name", "country",
    }
    assert set(event.keys()) == expected_keys


def test_user_id_is_from_user_pool():
    event = generate_event()
    assert event["user_id"] in USER_POOL


def test_session_id_is_valid_uuid():
    event = generate_event()
    # Will raise ValueError if not a valid UUID string
    parsed = uuid.UUID(event["session_id"])
    assert str(parsed) == event["session_id"]


def test_timestamp_is_valid_iso_format():
    event = generate_event()
    # Will raise ValueError if not valid ISO 8601
    parsed = datetime.fromisoformat(event["timestamp"])
    assert parsed.tzinfo is not None  # must be timezone-aware


def test_event_type_is_valid():
    event = generate_event()
    assert event["event_type"] in EVENT_TYPES


def test_plan_tier_is_valid():
    event = generate_event()
    assert event["plan_tier"] in PLAN_TIERS


def test_country_is_valid():
    event = generate_event()
    assert event["country"] in COUNTRIES


def test_feature_name_only_set_for_feature_used_events():
    """
    feature_name should be None for all event types except
    'feature_used', where it should be one of FEATURE_NAMES.
    """
    # Generate many events to ensure we observe both cases
    events = [generate_event() for _ in range(200)]

    feature_used_events = [e for e in events if e["event_type"] == "feature_used"]
    other_events = [e for e in events if e["event_type"] != "feature_used"]

    # Sanity check: with 200 samples and feature_used weighted at 50/100,
    # we should see both groups represented
    assert len(feature_used_events) > 0
    assert len(other_events) > 0

    for event in feature_used_events:
        assert event["feature_name"] in FEATURE_NAMES

    for event in other_events:
        assert event["feature_name"] is None


def test_event_type_distribution_roughly_matches_weights():
    """
    With a large sample, feature_used (weight 50/100) should be the most
    common event type, and signup (weight 2/100) should be the rarest.
    This is a statistical sanity check, not an exact assertion -- it uses
    a large sample size and generous bounds to avoid flaky failures.
    """
    events = [generate_event() for _ in range(2000)]
    counts = {et: 0 for et in EVENT_TYPES}
    for e in events:
        counts[e["event_type"]] += 1

    # feature_used should be the most frequent event type
    assert counts["feature_used"] == max(counts.values())

    # signup should be among the least frequent (weight=2, smallest)
    assert counts["signup"] <= counts["feature_used"]
    assert counts["signup"] <= counts["login"]
