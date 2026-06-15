"""
kafka_producer.py

Continuously generates synthetic SaaS user events and publishes them to the
Kafka topic 'user-events'. Simulates the event stream a real SaaS application
backend would send to a tracking pipeline (e.g. Segment, Snowplow).

Usage:
    python producer/kafka_producer.py
"""

import json
import time
import logging

from kafka import KafkaProducer
from event_generator import generate_event

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(message)s")
logging.getLogger(__name__).setLevel(logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC_NAME = "user-events"

# Target ~1000 events/minute -> ~16-17 events/second -> small delay between sends
EVENTS_PER_MINUTE = 1000
SLEEP_INTERVAL = 60 / EVENTS_PER_MINUTE  # seconds between each event


def create_producer() -> KafkaProducer:
    """
    Create and return a configured KafkaProducer.

    Configuration choices explained:
    - value_serializer: converts our Python dict to JSON bytes before sending,
      since Kafka transmits raw bytes.
    - acks='all': the producer waits for the leader AND all in-sync replicas
      to acknowledge the write. This is the strongest durability guarantee
      Kafka offers (at the cost of some latency). In production, this
      prevents data loss if a broker fails right after a write.
    - retries=5: if a send fails transiently (e.g. broker temporarily
      unavailable), retry up to 5 times before giving up.
    """
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",
        retries=5,
    )


def run_producer():
    """
    Run an infinite loop generating and sending events to Kafka.

    Each event's user_id is used as the Kafka message key. This ensures all
    events for the same user land on the same partition (Kafka guarantees
    ordering within a partition) -- useful later for session/user-level
    analysis in Spark.
    """
    producer = create_producer()
    logger.info(f"Starting producer -> topic '{TOPIC_NAME}' at ~{EVENTS_PER_MINUTE} events/min")

    event_count = 0
    try:
        while True:
            event = generate_event()

            producer.send(
                TOPIC_NAME,
                key=event["user_id"],
                value=event,
            )

            event_count += 1
            if event_count % 100 == 0:
                logger.info(f"Sent {event_count} events so far. Last event: {event}")

            time.sleep(SLEEP_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Stopping producer (KeyboardInterrupt received)...")
    finally:
        producer.flush()
        producer.close()
        logger.info(f"Producer closed. Total events sent: {event_count}")


if __name__ == "__main__":
    run_producer()
