"""Tests for the Validation Result Consumer's commit-after-processing logic.
Offline: mocked consumer/producer, SPARQL update patched out.
"""
from __future__ import annotations

from unittest import mock

from kafka.structs import OffsetAndMetadata, TopicPartition

from services.validation_consumer import main as vc
from services.validation_consumer.config import ValidationConsumerConfig

VALID_DECISION = {
    "annotation_id": "annotation_a1",
    "document_id": "d12345",
    "decision_id": "g00042",
    "outcome": "validated",
    "method": "quadratic_voting",
    "quorum_reached": True,
    "reputation_snapshot_id": "r00042",
    "ledger_anchor": "0xA1B2C3",
    "decided_at": "2026-08-25T10:14:00Z",
}


class _Msg:
    def __init__(self, value, topic="fen.governance.decisions.v1", partition=0, offset=0):
        self.value = value
        self.topic = topic
        self.partition = partition
        self.offset = offset


class _Consumer:
    def __init__(self, records):
        self._records = records
        self.committed = []

    def poll(self, timeout_ms=None, max_records=None):
        return self._records

    def commit(self, offsets=None):
        self.committed.append(offsets)


class _Producer:
    def __init__(self):
        self.sent = []

    def send(self, topic, value=None, key=None):
        self.sent.append((topic, value, key))
        return None


def _config() -> ValidationConsumerConfig:
    return ValidationConsumerConfig.from_env()


def test_handle_message_publishes_entity_validated_confirmation():
    producer = _Producer()
    with mock.patch.object(vc, "apply_update", return_value=None):
        vc.handle_message(_config(), producer, VALID_DECISION)

    assert len(producer.sent) == 1
    topic, payload, _ = producer.sent[0]
    assert topic == "dap.entities.validated.v1"
    assert payload["annotation_id"] == "annotation_a1"
    assert payload["document_id"] == "d12345"
    assert payload["decision_id"] == "g00042"
    assert payload["outcome"] == "validated"


def test_process_cycle_commits_each_message_after_processing():
    records = {None: [_Msg(VALID_DECISION, offset=10), _Msg(VALID_DECISION, offset=11)]}
    consumer = _Consumer(records)
    producer = _Producer()

    with mock.patch.object(vc, "apply_update", return_value=None) as updater:
        vc.process_cycle(_config(), consumer, producer)

    assert updater.call_count == 2
    assert len(producer.sent) == 2
    assert len(consumer.committed) == 2
    assert consumer.committed[0] == {
        TopicPartition("fen.governance.decisions.v1", 0): OffsetAndMetadata(offset=11, leader_epoch=0, metadata="")
    }
    assert consumer.committed[1] == {
        TopicPartition("fen.governance.decisions.v1", 0): OffsetAndMetadata(offset=12, leader_epoch=0, metadata="")
    }


def test_process_cycle_stops_and_does_not_commit_after_failure():
    """At-least-once: a message that fails to process is logged loudly, its
    offset (and anything after it in the batch) stays uncommitted and is
    redelivered."""
    records = {
        None: [
            _Msg(VALID_DECISION, offset=10),
            _Msg({**VALID_DECISION, "annotation_id": "poisoned"}, offset=11),
            _Msg(VALID_DECISION, offset=12),
        ]
    }
    consumer = _Consumer(records)
    producer = _Producer()
    real_handle = vc.handle_message

    def flaky(config, producer, payload):
        if payload.get("annotation_id") == "poisoned":
            raise RuntimeError("SPARQL update failed")
        return real_handle(config, producer, payload)

    with mock.patch.object(vc, "apply_update", return_value=None):
        with mock.patch.object(vc, "handle_message", side_effect=flaky):
            vc.process_cycle(_config(), consumer, producer)

    # only the first (successful) message was committed; the third was never
    # reached because the cycle stops at the first failure.
    assert len(consumer.committed) == 1
    assert len(producer.sent) == 1
