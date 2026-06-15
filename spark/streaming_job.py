"""
streaming_job.py

Spark Structured Streaming job that reads SaaS user events from the Kafka
topic 'user-events', parses the JSON payload, and computes real-time KPIs
using windowed aggregations.

Run inside the Spark container via spark-submit, e.g.:

    docker exec streaming-spark /opt/spark/bin/spark-submit \\
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \\
        /opt/spark-apps/streaming_job.py
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, count
from pyspark.sql.types import StructType, StructField, StringType, TimestampType

# --- Schema definition ---
# This mirrors the event schema produced by producer/event_generator.py.
# Defining an explicit schema (rather than letting Spark infer it) is a
# best practice: it's faster, and it fails loudly if upstream data changes
# shape unexpectedly -- a real "data contract" between teams.
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


def main():
    # SparkSession is the entry point to all Spark functionality.
    spark = SparkSession.builder \
        .appName("SaaSEventStreamProcessor") \
        .getOrCreate()

    # Reduce noisy Spark logs so our own output is easier to read.
    spark.sparkContext.setLogLevel("WARN")

    # --- Read from Kafka ---
    # Spark treats this as a streaming DataFrame: an unbounded table that
    # grows as new Kafka messages arrive. Each row initially has columns
    # like 'key', 'value' (both binary), 'topic', 'partition', 'offset', etc.
    raw_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", TOPIC_NAME) \
        .option("startingOffsets", "latest") \
        .load()

    # --- Parse JSON payload ---
    # Kafka's 'value' column is raw bytes -> cast to string -> parse as JSON
    # using our event_schema -> expand into individual columns.
    parsed_stream = raw_stream.select(
        from_json(col("value").cast("string"), event_schema).alias("data")
    ).select("data.*")

    # --- Windowed aggregation: events per minute ---
    # Watermarking tells Spark to wait up to 1 minute for late-arriving
    # events (e.g. network delays) before finalizing a window's count.
    # Without this, Spark would hold state for these windows forever.
    events_per_minute = parsed_stream \
        .withWatermark("timestamp", "1 minute") \
        .groupBy(window(col("timestamp"), "1 minute")) \
        .agg(count("*").alias("event_count"))

    # --- Output to console for debugging ---
    # outputMode("update") emits updated aggregation results as new data
    # arrives within the watermark window (vs "complete" which re-emits
    # the entire result table every trigger -- too verbose here).
    query = events_per_minute.writeStream \
        .outputMode("update") \
        .format("console") \
        .option("truncate", "false") \
        .trigger(processingTime="10 seconds") \
        .start()

    query.awaitTermination()


if __name__ == "__main__":
    main()
