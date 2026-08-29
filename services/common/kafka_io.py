"""Thin consumer/producer wrappers over kafka-python, shared by the FEN
Bridge and the Validation Result Consumer (AGENT_PLAN.md, Phase 2, task 2),
with explicit at-least-once delivery guarantees.

Producer side (``make_producer``): ``acks='all'`` + ``retries`` with
``enable_idempotence=True`` — the broker acks only once every in-sync replica
holds the record, and idempotence prevents duplicates from producer-side
retries (no at-most-once gaps, no duplicate storms).

Consumer side (``make_consumer``): ``enable_auto_commit=False`` — offsets are
committed ONLY *after* a batch/message has been fully processed
(commit-after-processing). A crash or failure between processing and commit
therefore redelivers the message: exactly-once is out of scope, at-least-once
is guaranteed. Consumers that need delivery coordinates use
``poll_batch_with_offsets`` + ``commit_offsets``; ``poll_batch`` remains for
callers that only need values.

Kept in ``services.common`` so neither service package imports from the other
(guardrail: fen_bridge and validation_consumer stay fully independent).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, NamedTuple, Optional

from kafka import KafkaConsumer, KafkaProducer
from kafka.structs import OffsetAndMetadata, TopicPartition

logger = logging.getLogger(__name__)


class MessageRecord(NamedTuple):
    """A decoded Kafka message plus its delivery coordinates (topic,
    partition, offset) so consumers can commit exactly the offsets they
    processed. ``key`` and ``timestamp`` mirror kafka-python's ConsumerRecord.
    """

    value: dict
    topic: str
    partition: int
    offset: int
    key: Optional[bytes] = None
    timestamp: Optional[int] = None


def make_consumer(
    bootstrap_servers: str,
    topic: str,
    group_id: str,
    auto_offset_reset: str = "latest",
    enable_auto_commit: bool = False,
) -> KafkaConsumer:
    """Create a consumer with manual offset management (default
    ``enable_auto_commit=False``): offsets are committed only after a message
    or batch has been fully processed — the commit-after-processing pattern
    that yields at-least-once delivery. Pass ``enable_auto_commit=True`` only
    if a caller deliberately opts into at-most-once behaviour.
    """
    return KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        enable_auto_commit=enable_auto_commit,
        auto_offset_reset=auto_offset_reset,
    )


def poll_batch(consumer: KafkaConsumer, batch_size: int, poll_timeout_ms: int) -> List[dict]:
    """Poll up to ``batch_size`` decoded message *values*. Backward-compatible
    with the original contract used by services/fen_bridge/outbound.py; prefer
    ``poll_batch_with_offsets`` when you need delivery coordinates for manual
    offset commits.
    """
    return [record.value for record in poll_batch_with_offsets(consumer, batch_size, poll_timeout_ms)]


def poll_batch_with_offsets(
    consumer: KafkaConsumer,
    batch_size: int,
    poll_timeout_ms: int,
) -> List[MessageRecord]:
    """Poll up to ``batch_size`` messages as ``MessageRecord``s carrying
    topic/partition/offset alongside the decoded value. Transient poll errors
    are logged and yield an empty batch — the loop must never die on a broker
    blip (matches the "no blocking points" principle, D2.2 section 4.1).
    """
    batch: List[MessageRecord] = []
    try:
        records = consumer.poll(timeout_ms=poll_timeout_ms, max_records=batch_size)
    except Exception:  # noqa: BLE001 - broker hiccups must not kill the loop
        logger.exception("poll failed; returning empty batch")
        return batch
    for _topic_partition, messages in records.items():
        for message in messages:
            batch.append(
                MessageRecord(
                    value=message.value,
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                    key=getattr(message, "key", None),
                    timestamp=getattr(message, "timestamp", None),
                )
            )
            if len(batch) >= batch_size:
                return batch
    return batch


def commit_offsets(consumer: KafkaConsumer, records: List[MessageRecord]) -> None:
    """Commit the offset *after* each record in ``records`` — explicit
    per-record offsets, NOT the consumer position, so a record that failed
    earlier in the same poll stays uncommitted and is redelivered
    (at-least-once). ``records`` must come from ``poll_batch_with_offsets``.
    """
    offsets = {
        TopicPartition(record.topic, record.partition): OffsetAndMetadata(
            offset=record.offset + 1, metadata="", leader_epoch=0
        )
        for record in records
    }
    consumer.commit(offsets=offsets)
    logger.debug("committed offsets %s", offsets)


def make_producer(bootstrap_servers: str) -> KafkaProducer:
    """Create a producer with at-least-once delivery settings: ``acks='all'``
    (the leader waits for all in-sync replicas before acking), ``retries=5``
    with ``enable_idempotence=True`` (producer-side retries never duplicate a
    record), and a small ``linger_ms`` that batches messages without adding
    noticeable latency.
    """
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, default=_json_default).encode("utf-8"),
        acks="all",
        retries=5,
        linger_ms=50,
        enable_idempotence=True,
    )


def send(producer: KafkaProducer, topic: str, payload: dict, key: Optional[bytes] = None) -> None:
    """Fire-and-forget send with delivery logging: both success and terminal
    KafkaError failures are surfaced through callbacks, so broker-side
    delivery problems are visible in the logs instead of silently dropped.
    Transient errors are already retried inside the producer (see
    ``make_producer``); the errback only reports the failures that remain.
    """
    future = producer.send(topic, value=payload, key=key)
    add_callback = getattr(future, "add_callback", None)
    add_errback = getattr(future, "add_errback", None)
    if add_callback is None or add_errback is None:
        # e.g. a test double whose send() returns None — nothing to attach to.
        return
    add_callback(_log_delivery_success)
    add_errback(_log_delivery_error)


def _log_delivery_success(metadata) -> None:
    """Log a confirmed delivery. Runs on the producer's I/O thread — must
    never raise.
    """
    logger.info("delivered to %s[%d] at offset %d", metadata.topic, metadata.partition, metadata.offset)


def _log_delivery_error(exc: Exception) -> None:
    """Log a terminal delivery failure (a KafkaError that survived the
    producer's retries). Runs on the producer's I/O thread — must never
    raise.
    """
    logger.error("Kafka delivery failed: %s", exc)


def _json_default(obj):
    """``json.dumps`` default for non-serializable objects: datetimes (e.g.
    ``GovernanceDecision.decided_at``) become ISO-8601 strings so the webhook
    can publish full decision payloads to Kafka.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")