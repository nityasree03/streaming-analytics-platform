"""
app.py

Streamlit Executive Overview dashboard for the Real-Time Streaming
Analytics Platform. Reads aggregated KPIs from PostgreSQL (written by
the Spark Structured Streaming job) and displays them as live-updating
charts and KPI cards.

Run with:
    streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import nl_to_sql
import plotly.express as px
from datetime import datetime, timezone

# --- Page config ---
st.set_page_config(
    page_title="SaaS Analytics Platform",
    page_icon="📊",
    layout="wide",
)

# --- Postgres connection ---
# Database connection config. On Streamlit Community Cloud, these values
# come from st.secrets (configured in the app's "Secrets" settings, using
# TOML format -- see dashboard/README.md for the expected keys). When
# running locally, st.secrets falls back to these defaults pointing at
# the docker-compose Postgres (host-mapped to localhost:5433).
def _get_pg_config():
    try:
        return {
            "host": st.secrets["postgres"]["host"],
            "port": st.secrets["postgres"]["port"],
            "dbname": st.secrets["postgres"]["dbname"],
            "user": st.secrets["postgres"]["user"],
            "password": st.secrets["postgres"]["password"],
        }
    except (KeyError, FileNotFoundError):
        return {
            "host": "localhost",
            "port": 5433,
            "dbname": "streaming_analytics",
            "user": "streaming_user",
            "password": "streaming_pass",
        }


PG_CONFIG = _get_pg_config()


def load_aggregated_metrics() -> pd.DataFrame:
    """
    Open a fresh connection and load all rows from aggregated_metrics.

    A new connection is opened on each call (rather than cached) because
    this function runs inside an auto-refreshing fragment -- a cached
    connection can go stale across refresh cycles. Connections to a
    local Postgres are cheap enough that this isn't a performance concern
    at this scale.
    """
    engine = create_engine(
        f"postgresql+psycopg2://{PG_CONFIG['user']}:{PG_CONFIG['password']}"
        f"@{PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']}?sslmode=require"
    )
    query = """
        SELECT window_start, window_end, metric_name, metric_value
        FROM aggregated_metrics
        WHERE metric_name = 'events_per_minute'
        ORDER BY window_start
    """
    df = pd.read_sql(query, engine)
    return df


@st.fragment(run_every="5s")
def live_dashboard():
    """
    The auto-refreshing portion of the dashboard. Everything inside this
    function reruns every 5 seconds without reloading the whole page
    (e.g. the title and static text above stay put).
    """
    st.caption(
        f"Last refreshed: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} "
        f"(auto-refreshes every 5 seconds)"
    )

    df = load_aggregated_metrics()

    if df.empty:
        st.warning(
            "No data yet. Make sure the producer and Spark streaming "
            "job are running, then wait ~1 minute for the first window "
            "to close."
        )
        return

    # --- KPI cards ---
    latest = df.iloc[-1]
    total_events = int(df["metric_value"].sum())
    avg_events_per_minute = df["metric_value"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Events (all windows)", f"{total_events:,}")
    col2.metric("Latest Window Events", f"{int(latest['metric_value']):,}")
    col3.metric("Avg Events / Minute", f"{avg_events_per_minute:,.0f}")

    # --- Time series chart ---
    st.subheader("Events Per Minute (Live)")
    fig = px.line(
        df,
        x="window_start",
        y="metric_value",
        markers=True,
        labels={"window_start": "Window Start (UTC)", "metric_value": "Event Count"},
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, width='stretch')

    # --- Raw data table (collapsible) ---
    with st.expander("Raw aggregated_metrics data"):
        st.dataframe(df, width='stretch')


def ask_question_section():
    """
    Renders the "Ask a Question" natural-language-to-SQL section.
    Takes a plain-English question, generates a read-only SQL query via
    the Anthropic API (dashboard.nl_to_sql), executes it against
    Postgres, and displays the results alongside the generated SQL for
    transparency.
    """
    st.divider()
    st.subheader("🤖 Ask a Question (AI-Powered)")
    st.caption(
        "Ask a question in plain English and Claude will generate a SQL "
        "query to answer it. Example: \"How many users are on the free plan?\""
    )

    question = st.text_input("Your question", placeholder="e.g. Which feature is used most often?")

    if st.button("Ask") and question:
        try:
            sql = nl_to_sql.generate_sql(question)
        except nl_to_sql.SQLGenerationError as e:
            st.error(str(e))
            return

        st.code(sql, language="sql")

        try:
            engine = create_engine(
                f"postgresql+psycopg2://{PG_CONFIG['user']}:{PG_CONFIG['password']}"
                f"@{PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']}?sslmode=require"
            )
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION READ ONLY"))
                result_df = pd.read_sql(sql, conn)
            st.dataframe(result_df, width='stretch')
        except Exception as e:
            st.error(f"Query execution failed: {e}")


def main():
    st.title("📊 SaaS Product Analytics — Executive Overview")
    st.markdown(
        "Real-time event pipeline: **Kafka → Spark Structured Streaming → PostgreSQL**"
    )
    live_dashboard()
    ask_question_section()


if __name__ == "__main__":
    main()
