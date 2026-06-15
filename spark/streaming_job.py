"""
streaming_job.py

Spark Structured Streaming job that reads SaaS user events from the Kafka
topic 'user-events', parses the JSON payload, computes real-time KPIs using
windowed aggregations, and upserts results into PostgreSQL.

Run inside the Spark container via spark-submit, e.g.:

    docker exec streaming-spark /opt/spark/bin/spark-submit \\
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.postgresql:postgresql:42.7.3 \\
        /opt/spark-apps/streaming_job.py
"""

import psycopg2
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, count
from pyspark.sql.types import StructType, StructField, StringType, TimestampType

# --- Schema definition ---
# Mirrors the event schema produced by producer/event_generator.py.
event_schema = StructType([
    StructField("user_id", StringType(), True),
    StructField("session_id", StringType(), True),
    StructField("timestamp", TimestampType(), True),
    StructField("event_type", StringType(), True),
    StructField("plan_tier", StringType(), True),
    StructField("feature_name", StringType(), True),
    StructField("country", StringType(), True),
])

KAFKA_BOOTSTRAP_SERVERS = "kafka:29092"
TOPIC_NAME = "user-events"

# Postgres connection details for the streaming-postgres container.
# 'postgres' is the Docker Compose service name -- Spark resolves this
# via the shared Docker network, just like 'kafka' for the broker.
PG_CONFIG = {
    "host": "postgres",
    "port": 5432,
    "dbname": "streaming_analytics",
    "user": "streaming_user",
    "password": "streaming_pass",
}

# JDBC connection string for the raw_events append-only writer.
JDBC_URL = "jdbc:postgresql://postgres:5432/streaming_analytics"
JDBC_PROPERTIES = {
    "user": "streaming_user",
    "password": "streaming_pass",
    "driver": "org.postgresql.Driver",
}

UPSERT_SQL = """
    INSERT INTO aggregated_metrics (window_start, window_end, metric_name, metric_value)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (window_start, window_end, metric_name)
    DO UPDATE SET metric_value = EXCLUDED.metric_value
"""


def write_to_postgres(batch_df, batch_id):
    """
    Called once per micro-batch by foreachBatch. Upserts the windowed
    event-count aggregation into the aggregated_metrics table.

    We use a raw psycopg2 upsert (INSERT ... ON CONFLICT ... DO UPDATE)
    rather than Spark's JDBC writer, because Structured Streaming's
    outputMode("update") re-emits a window's row every time its count
    changes (as late-arriving events update the running total). A plain
    INSERT would violate the UNIQUE constraint on the second emission
    for the same window; an upsert correctly overwrites the value.

    Collecting to the driver is safe here because the aggregation only
    produces a handful of rows per batch (one per active window).
    """
    rows = batch_df.collect()
    if not rows:
        return

    conn = psycopg2.connect(**PG_CONFIG)
    try:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(UPSERT_SQL, (
                    row["window"]["start"],
                    row["window"]["end"],
                    "events_per_minute",
                    float(row["event_count"]),
                ))
        conn.commit()
    finally:
        conn.close()

    print(f"Batch {batch_id}: upserted {len(rows)} row(s) into aggregated_metrics")


def write_raw_events(batch_df, batch_id):
    """
    Called once per micro-batch by foreachBatch. Appends raw parsed events
    to the raw_events table for full-fidelity historical analysis (DAU,
    MAU, retention, funnels -- queries that need event-level granularity
    rather than pre-aggregated windows).
    """
    if batch_df.isEmpty():
        return

    output_df = batch_df.select(
        col("user_id").cast("string"),
        col("session_id").cast("string"),
        col("timestamp").alias("event_timestamp"),
        col("event_type"),
        col("plan_tier"),
        col("feature_name"),
        col("country"),
    )

    output_df.write \
        .mode("append") \
        .jdbc(url=JDBC_URL, table="raw_events", properties=JDBC_PROPERTIES)

    print(f"Batch {batch_id}: appended {output_df.count()} row(s) to raw_events")


def main():
    spark = SparkSession.builder \
        .appName("SaaSEventStreamProcessor") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    # --- Read from Kafka ---
    raw_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", TOPIC_NAME) \
        .option("startingOffsets", "latest") \
        .load()

    # --- Parse JSON payload ---
    parsed_stream = raw_stream.select(
        from_json(col("value").cast("string"), event_schema).alias("data")
    ).select("data.*")

    # --- Windowed aggregation: events per minute ---
    events_per_minute = parsed_stream \
        .withWatermark("timestamp", "1 minute") \
        .groupBy(window(col("timestamp"), "1 minute")) \
        .agg(count("*").alias("event_count"))

    # --- Upsert aggregated metrics into PostgreSQL via foreachBatch ---
    metrics_query = events_per_minute.writeStream \
        .outputMode("update") \
        .foreachBatch(write_to_postgres) \
        .trigger(processingTime="10 seconds") \
        .start()

    # --- Append raw events into PostgreSQL via foreachBatch ---
    raw_events_query = parsed_stream.writeStream \
        .outputMode("append") \
        .foreachBatch(write_raw_events) \
        .trigger(processingTime="10 seconds") \
        .start()

    # Wait for both streaming queries to run indefinitely.
    metrics_query.awaitTermination()
    raw_events_query.awaitTermination()


if __name__ == "__main__":
    main()
