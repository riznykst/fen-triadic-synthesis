"""Compatibility shim — the implementation lives in services.common.kafka_io.
Kept at the AGENT_PLAN.md Phase 2 path so imports keep working; the real code
is single-sourced in services/common.
"""
from services.common.kafka_io import make_consumer, make_producer, poll_batch, send  # noqa: F401

__all__ = ["make_consumer", "make_producer", "poll_batch", "send"]
