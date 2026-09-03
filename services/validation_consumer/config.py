"""Env-driven settings for the Validation Result Consumer."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ValidationConsumerConfig:
    kafka_bootstrap_servers: str
    topic_governance_decisions: str
    topic_validated: str
    sparql_update_endpoint: str
    sparql_update_user: str
    sparql_update_password: str
    consumer_group_id: str
    batch_size: int
    poll_timeout_ms: int

    @classmethod
    def from_env(cls) -> "ValidationConsumerConfig":
        return cls(
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            topic_governance_decisions=os.getenv("TOPIC_GOVERNANCE_DECISIONS", "fen.governance.decisions.v1"),
            topic_validated=os.getenv("TOPIC_VALIDATED")
            or os.getenv("FEN_TOPIC_VALIDATED") or "dap.entities.validated.v1",
            sparql_update_endpoint=os.getenv("SPARQL_UPDATE_ENDPOINT", "http://localhost:3030/fen/update"),
            sparql_update_user=os.getenv("SPARQL_UPDATE_USER", ""),
            sparql_update_password=os.getenv("SPARQL_UPDATE_PASSWORD", ""),
            # Mirror FenBridgeConfig hygiene: poll tuning and the consumer
            # group id are env-driven (TECH-DEBT P2 config hygiene), so
            # parallel test deployments can use a distinct group.
            consumer_group_id=os.getenv("FEN_CONSUMER_GROUP_ID", "validation-consumer"),
            batch_size=int(os.getenv("FEN_CONSUMER_BATCH_SIZE", "10")),
            poll_timeout_ms=int(os.getenv("FEN_CONSUMER_POLL_TIMEOUT_MS", "1000")),
        )
