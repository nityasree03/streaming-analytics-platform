"""
event_generator.py

Generates synthetic SaaS product usage events for the streaming analytics platform.

Each event represents a single user action (signup, login, feature use,
upgrade, purchase, or logout) — mimicking what a real event-tracking system
(e.g. Segment, Amplitude, Snowplow) would emit from a SaaS application.
"""

import random
import uuid
from datetime import datetime, timezone
from faker import Faker

fake = Faker()

# --- Configuration ---

# A fixed pool of user IDs simulates a real user base where the same
# users return across multiple sessions/events (needed for DAU/MAU,
# retention, and conversion metrics later).
NUM_USERS = 500
USER_POOL = [str(uuid.uuid4()) for _ in range(NUM_USERS)]

EVENT_TYPES = [
    "signup",
    "login",
    "feature_used",
    "upgrade",
    "purchase",
    "logout",
]

# Weighted so that "feature_used" and "login" dominate (realistic for SaaS:
# most events are usage events, not signups/upgrades).
EVENT_TYPE_WEIGHTS = [2, 25, 50, 5, 8, 10]

PLAN_TIERS = ["free", "basic", "pro", "enterprise"]
PLAN_TIER_WEIGHTS = [60, 20, 15, 5]  # most users are on free plans

FEATURE_NAMES = [
    "dashboard_view",
    "export_report",
    "create_project",
    "invite_teammate",
    "api_integration",
    "advanced_filters",
    "custom_branding",
    "bulk_import",
]

COUNTRIES = ["US", "GB", "IN", "DE", "CA", "AU", "BR", "FR", "JP", "MX"]


def generate_event() -> dict:
    """
    Generate a single synthetic SaaS event as a dictionary.

    Returns:
        dict: An event matching the schema:
            user_id, session_id, timestamp, event_type,
            plan_tier, feature_name, country
    """
    event_type = random.choices(EVENT_TYPES, weights=EVENT_TYPE_WEIGHTS, k=1)[0]

    event = {
        "user_id": random.choice(USER_POOL),
        "session_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "plan_tier": random.choices(PLAN_TIERS, weights=PLAN_TIER_WEIGHTS, k=1)[0],
        "feature_name": random.choice(FEATURE_NAMES) if event_type == "feature_used" else None,
        "country": random.choice(COUNTRIES),
    }

    return event


if __name__ == "__main__":
    # Quick manual test: print 5 sample events
    for _ in range(5):
        print(generate_event())
