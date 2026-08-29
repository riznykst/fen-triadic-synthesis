"""Tests for the Kafka IO wrappers' delivery guarantees: producer config,
manual-commit consumer, offset-carrying polls, and delivery callbacks.
All offline — kafka-python classes are mocked/stubbed.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from kafka.errors import KafkaError
from kafka.structs import OffsetAndMetadata, TopicPartition

from services.common import kafka_io
from services.common.kafka_io import (
    MessageRecord,
    commit_offsets,
    poll_batch,
    poll_batch_with_offsets,
    send,
)


# ---- producer / consumer construction -----------------------------------


def test_make_producer_enables_at_least_once_guarantees(monkeypatch):
    captured = {}

    class _FakeKafkaProducer:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(kafka_io, "KafkaProducer", _FakeKafkaProducer)

    kafka_io.make_producer("localhost:9092")

    assert captured["acks"] == "all"
    assert captured["retries"] == 5
    assert captured["linger_ms"] == 50
    assert captured["enable_idempotence"] is True


def test_make_consumer_disables_auto_commit(monkeypatch):
    captured = {}

    class _FakeKafkaConsumer:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(kafka_io, "KafkaConsumer", _FakeKafkaConsumer)

    kafka_io.make_consumer("localhost:9092", "topic", "group")

    assert captured["enable_auto_commit"] is False


# ---- polling -------------------------------------------------------------


class _FakeMsg:
    def __init__(self, value, topic, partition, offset):
        self.value = value
        self.topic = topic
        self.partition = partition
        self.offset = offset


class _FakeConsumer:
    def __init__(self, records):
        self._records = records

    def poll(self, timeout_ms=None, max_records=None):
        return self._records


class _BrokenConsumer:
    def poll(self, timeout_ms=None, max_records=None):
        raise RuntimeError("broker blip")


def test_poll_batch_with_offsets_returns_delivery_coordinates():
    consumer = _FakeConsumer(
        {None: [_FakeMsg({"a": 1}, "t1", 0, 41), _FakeMsg({"a": 2}, "t1", 0, 42)]}
    )

    batch = poll_batch_with_offsets(consumer, batch_size=10, poll_timeout_ms=1000)

    assert batch == [
        MessageRecord(value={"a": 1}, topic="t1", partition=0, offset=41),
        MessageRecord(value={"a": 2}, topic="t1", partition=0, offset=42),
    ]


def test_poll_batch_returns_values_only_compat():
    """poll_batch keeps its original values-only contract (outbound.py)."""
    consumer = _FakeConsumer({None: [_FakeMsg({"a": 1}, "t1", 0, 41)]})

    assert poll_batch(consumer, batch_size=10, poll_timeout_ms=1000) == [{"a": 1}]


def test_poll_batch_caps_at_batch_size():
    consumer = _FakeConsumer({None: [_FakeMsg({"a": i}, "t1", 0, i) for i in range(5)]})

    assert len(poll_batch_with_offsets(consumer, batch_size=2, poll_timeout_ms=1000)) == 2


def test_poll_batch_survives_broker_blips():
    assert poll_batch_with_offsets(_BrokenConsumer(), batch_size=10, poll_timeout_ms=1000) == []


# ---- explicit offset commits ---------------------------------------------


class _CommittingConsumer(_FakeConsumer):
    def __init__(self, records):
        super().__init__(records)
        self.committed = None

    def commit(self, offsets=None):
        self.committed = offsets


def test_commit_offsets_commits_offset_after_each_record():
    consumer = _CommittingConsumer({None: [_FakeMsg({"a": 1}, "t1", 3, 41)]})
    records = poll_batch_with_offsets(consumer, batch_size=10, poll_timeout_ms=1000)

    commit_offsets(consumer, records)

    assert consumer.committed == {TopicPartition("t1", 3): OffsetAndMetadata(offset=42, leader_epoch=0, metadata="")}


# ---- send() delivery callbacks -------------------------------------------


class _FakeFuture:
    def __init__(self):
        self.callbacks = []
        self.errbacks = []

    def add_callback(self, fn):
        self.callbacks.append(fn)

    def add_errback(self, fn):
        self.errbacks.append(fn)


class _FakeProducer:
    def __init__(self, future=None):
        self._future = future
        self.sent = []

    def send(self, topic, value=None, key=None):
        self.sent.append((topic, value, key))
        return self._future


def test_send_attaches_delivery_callbacks():
    future = _FakeFuture()
    producer = _FakeProducer(future)

    send(producer, "t", {"a": 1})

    assert len(future.callbacks) == 1
    assert len(future.errbacks) == 1
    assert producer.sent == [("t", {"a": 1}, None)]


def test_send_logs_delivery_success(caplog):
    future = _FakeFuture()
    producer = _FakeProducer(future)

    with caplog.at_level(logging.INFO, logger="services.common.kafka_io"):
        send(producer, "t", {"a": 1})
        future.callbacks[0](SimpleNamespace(topic="t", partition=0, offset=7))

    assert "delivered to t[0] at offset 7" in caplog.text


def test_send_logs_delivery_error_without_raising(caplog):
    future = _FakeFuture()
    producer = _FakeProducer(future)

    with caplog.at_level(logging.ERROR, logger="services.common.kafka_io"):
        send(producer, "t", {"a": 1})
        future.errbacks[0](KafkaError("Broker: Not enough replicas"))

    assert "Kafka delivery failed" in caplog.text
    assert "Broker: Not enough replicas" in caplog.text


def test_send_tolerates_producer_without_future():
    """Test doubles whose send() returns None must not break the callers."""
    send(_FakeProducer(future=None), "t", {"a": 1})  # must not raise
