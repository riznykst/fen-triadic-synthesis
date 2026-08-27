"""Thin consumer/producer wrappers over kafka-python, shared by the FEN
Bridge and the Validation Result Consumer (AGENT_PLAN.md, Phase 2, task 2).
Kept in ``services.common`` so neither service package imports from the other
(guardrail: fen_bridge and validation_consumer stay fully independent).
"""
from __future__ import annotations

import json
import logging
from typing import List

from kafka import KafkaConsumer, KafkaProducer

logger = logging.getLogger(__name__)


def make_consumer(
    bootstrap_servers: str,
    topic: str,
    group_id: str,
    auto_offset_reset: str = "latest",
) -> KafkaConsumer:
    return KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset=auto_offset_reset,
    )


def poll_batch(consumer: KafkaConsumer, batch_size: int, poll_timeout_ms: int) -> List[dict]:
    """Poll up to ``batch_size`` decoded messages. Transient poll errors are
    logged and yield an empty batch — the loop must never die on a broker
    blip (matches the "no blocking points" principle, D2.2 section 4.1).
    """
    batch: List[dict] = []
    try:
        records = consumer.poll(timeout_ms=poll_timeout_ms, max_records=batch_size)
    except Exception:  # noqa: BLE001 - broker hiccups must not kill the loop
        logger.exception("poll failed; returning empty batch")
        return batch
    for messages in records.values():
        for message in messages:
            batch.append(message.value)
            if len(batch) >= batch_size:
                return batch
    return batch


def make_producer(bootstrap_servers: str) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def send(producer: KafkaProducer, topic: str, payload: dict) -> None:
    """Fire-and-forget send; delivery is async (Kafka producer buffers)."""
    producer.send(topic, value=payload)
