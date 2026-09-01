"""Env-driven settings for both FEN Bridge processes. No hardcoded hosts
(AGENT_PLAN.md, Phase 2, task 1).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class FenBridgeConfig:
    kafka_bootstrap_servers: str
    topic_pending_validation: str
    topic_governance_decisions: str
    fen_api_base_url: str
    consumer_group_id: str
    batch_size: int
    poll_timeout_ms: int
    fen_naan: str
    webhook_token: str


    @classmethod
    def from_env(cls) -> "FenBridgeConfig":
        return cls(
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            topic_pending_validation=os.getenv("TOPIC_PENDING_VALIDATION")
            or os.getenv("FEN_TOPIC_CANDIDATES") or "dap.entities.pending_validation.v1",
            topic_governance_decisions=os.getenv("TOPIC_GOVERNANCE_DECISIONS", "fen.governance.decisions.v1"),
            fen_api_base_url=os.getenv("FEN_API_BASE_URL", "http://localhost:8100"),
            consumer_group_id=os.getenv("FEN_BRIDGE_GROUP_ID", "fen-bridge-outbound"),
            batch_size=int(os.getenv("FEN_BRIDGE_BATCH_SIZE", "10")),
            poll_timeout_ms=int(os.getenv("FEN_BRIDGE_POLL_TIMEOUT_MS", "1000")),
            fen_naan=os.getenv("FEN_NAAN", "99999"),
            webhook_token=os.getenv("FEN_WEBHOOK_TOKEN", ""),
        )
