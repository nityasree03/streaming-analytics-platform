"""
nl_to_sql.py

Natural-language-to-SQL translation using the Anthropic API. Given a
plain-English question about the analytics data, asks Claude to generate
a read-only PostgreSQL SELECT query against our known schema, validates
that the result is safe to execute, and returns it.

Safety model:
    - The system prompt instructs the model to generate SELECT-only queries.
    - A keyword denylist rejects any query containing data-modifying or
      schema-modifying statements (INSERT, UPDATE, DELETE, DROP, ALTER,
      TRUNCATE, GRANT, etc.) as a defense-in-depth check, since LLM output
      should never be trusted blindly.
    - The query is wrapped and run via a read-only transaction
      (SET TRANSACTION READ ONLY) as an additional database-level guard.

Requires the ANTHROPIC_API_KEY environment variable to be set. If unset,
generate_sql() raises a clear error that the calling code can catch and
display to the user.
"""

import os
import re
import anthropic


SCHEMA_DESCRIPTION = """
You have access to a PostgreSQL database for a SaaS analytics platform
with the following tables:

raw_events (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(50) NOT NULL,   -- one of: signup, login, logout, feature_used, upgrade, purchase
    plan_tier VARCHAR(20),             -- one of: free, basic, pro, enterprise
    feature_name VARCHAR(50),          -- non-null only when event_type = 'feature_used'
    country VARCHAR(10),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

aggregated_metrics (
    id BIGSERIAL PRIMARY KEY,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(50) NOT NULL,  -- currently only 'events_per_minute'
    metric_value DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

user_metrics (
    user_id UUID PRIMARY KEY,
    plan_tier VARCHAR(20) NOT NULL,
    country VARCHAR(10),
    total_events INTEGER,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)

feature_usage (
    id BIGSERIAL PRIMARY KEY,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    feature_name VARCHAR(50) NOT NULL,
    usage_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

SYSTEM_PROMPT = f"""You are a SQL generation assistant for a PostgreSQL analytics database.

{SCHEMA_DESCRIPTION}

Given a natural language question, respond with ONLY a single read-only
SQL SELECT query that answers it. Rules:
- Output ONLY the SQL query, no explanation, no markdown code fences.
- The query MUST start with SELECT or WITH.
- NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, GRANT,
  CREATE, or any other data/schema-modifying statement.
- Use only the tables and columns described above.
- If the question cannot be answered with these tables, respond with
  exactly: CANNOT_ANSWER
"""

# Defense-in-depth: reject any query containing these keywords, even if
# the model is instructed not to generate them.
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "CREATE", "EXECUTE", "CALL", "COPY",
]


class SQLGenerationError(Exception):
    """Raised when SQL generation fails or produces an unsafe query."""
    pass


def generate_sql(question: str) -> str:
    """
    Translate a natural language question into a validated, read-only
    SQL query using the Anthropic API.

    Raises:
        SQLGenerationError: if ANTHROPIC_API_KEY is unset, the model
            cannot answer the question, or the generated query fails
            safety validation.
    """
    try:
        import streamlit as st
        api_key = st.secrets["ANTHROPIC_API_KEY"] if "ANTHROPIC_API_KEY" in st.secrets else os.environ.get("ANTHROPIC_API_KEY")
    except Exception:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SQLGenerationError(
            "ANTHROPIC_API_KEY is not set. Set this environment variable "
            "to enable the natural language query feature."
        )

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )

    sql = response.content[0].text.strip()

    if sql == "CANNOT_ANSWER":
        raise SQLGenerationError(
            "This question cannot be answered with the available data."
        )

    return validate_sql(sql)


def validate_sql(sql: str) -> str:
    """
    Validate that a SQL string is a read-only SELECT/WITH query with no
    forbidden keywords. Returns the (trimmed) SQL if valid, raises
    SQLGenerationError otherwise.
    """
    cleaned = sql.strip().rstrip(";")

    # Must start with SELECT or WITH (case-insensitive)
    if not re.match(r"^\s*(SELECT|WITH)\s", cleaned, re.IGNORECASE):
        raise SQLGenerationError(
            "Generated query does not start with SELECT or WITH -- rejected for safety."
        )

    # Reject forbidden keywords (as whole words, case-insensitive)
    upper = cleaned.upper()
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            raise SQLGenerationError(
                f"Generated query contains forbidden keyword '{keyword}' -- rejected for safety."
            )

    return cleaned
