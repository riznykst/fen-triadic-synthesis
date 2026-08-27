"""Validation Result Consumer.

Reads fen.governance.decisions.v1, applies the governance update into the
named graph via SPARQL (sparql_updater.py), then publishes an EntityValidated
confirmation to dap.entities.validated.v1.

Runs as the `validation-consumer` container (see docker-compose.yml).
"""
from __future__ import annotations

import logging
import time

from services.common import kafka_io
from services.common.messages import EntityValidated, GovernanceDecision
from services.validation_consumer.config import ValidationConsumerConfig
from services.validation_consumer.sparql_updater import apply_update, build_update_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def named_graph_uri(decision: GovernanceDecision) -> str:
    """The named graph the update is scoped to (D2.2 section 3.5: named
    graphs are the unit of update/replace/remove).
    """
    if decision.document_id:
        return f"urn:graphia:document:{decision.document_id}:graph"
    return f"urn:graphia:annotation:{decision.annotation_id}:graph"


def handle_decision(config: ValidationConsumerConfig, payload: dict) -> GovernanceDecision:
    """Validate the payload, build and execute the SPARQL update. Raises on
    failure — an update that silently fails would strand the entity at
    gfen:pending with no signal (see sparql_updater.apply_update docstring).
    """
    decision = GovernanceDecision.model_validate(payload)
    query = build_update_query(decision, named_graph_uri(decision))
    apply_update(config.sparql_update_endpoint, query)
    return decision


def main() -> None:
    config = ValidationConsumerConfig.from_env()
    consumer = kafka_io.make_consumer(
        config.kafka_bootstrap_servers,
        config.topic_governance_decisions,
        "validation-consumer",
    )
    producer = kafka_io.make_producer(config.kafka_bootstrap_servers)
    logger.info("validation-consumer started, watching %s", config.topic_governance_decisions)

    backoff_s = 1.0
    while True:
        try:
            batch = kafka_io.poll_batch(consumer, batch_size=10, poll_timeout_ms=1000)
            for payload in batch:
                decision = handle_decision(config, payload)
                confirmation = EntityValidated(
                    annotation_id=decision.annotation_id,
                    document_id=decision.document_id,
                    decision_id=decision.decision_id,
                    outcome=decision.outcome,
                )
                kafka_io.send(producer, config.topic_validated, confirmation.model_dump())
                logger.info(
                    "applied decision %s -> %s for %s",
                    decision.decision_id,
                    decision.outcome.value,
                    decision.annotation_id,
                )
            backoff_s = 1.0
        except Exception:  # noqa: BLE001 - keep consuming; failures are loud in logs
            logger.exception("consumer cycle failed; retrying in %.1fs", backoff_s)
            time.sleep(backoff_s)
            backoff_s = min(backoff_s * 2, 30.0)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
