"""Validation Result Consumer.

Reads fen.governance.decisions.v1, applies the governance update into the
named graph via SPARQL (sparql_updater.py), then publishes an EntityValidated
confirmation to dap.entities.validated.v1.

Runs as the `validation-consumer` container (see docker-compose.yml).

Delivery guarantee (at-least-once): each message's offset is committed only
AFTER it was fully processed (SPARQL update + EntityValidated published). A
failure is logged loudly and the offset is NOT committed, so the message is
redelivered on the next rebalance or restart.
"""
from __future__ import annotations

import logging
import signal
import threading
import time

from services.common import kafka_io
from services.common.logging_config import log_level_from_env, setup_logging
from services.common.messages import EntityValidated, GovernanceDecision
from services.common.metrics import KAFKA_MESSAGES_FAILED, KAFKA_MESSAGES_PROCESSED
from services.validation_consumer.config import ValidationConsumerConfig
from services.validation_consumer.sparql_updater import apply_update, build_update_query

setup_logging("validation-consumer", level=log_level_from_env())
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


def handle_message(config: ValidationConsumerConfig, producer, payload: dict) -> GovernanceDecision:
    """Full per-message pipeline: validate, apply the SPARQL update, publish
    the EntityValidated confirmation. Raises on failure — the caller leaves
    the message's offset uncommitted so it is redelivered (at-least-once).
    """
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
    return decision


def process_cycle(config: ValidationConsumerConfig, consumer, producer) -> None:
    """Poll one batch and process it message by message, committing each
    message's offset immediately after it was fully processed
    (commit-after-processing). On failure: log loudly and stop the cycle
    WITHOUT committing — the failed message, and anything after it in the
    batch, stays uncommitted and is redelivered. This is the pattern that
    gives the pipeline its at-least-once guarantee.
    """
    records = kafka_io.poll_batch_with_offsets(consumer, batch_size=10, poll_timeout_ms=1000)
    for record in records:
        try:
            handle_message(config, producer, record.value)
        except Exception:  # noqa: BLE001 - loud failure, no commit (at-least-once)
            KAFKA_MESSAGES_FAILED.inc()
            logger.exception(
                "failed to process message topic=%s partition=%d offset=%d; "
                "offset NOT committed — will be redelivered (at-least-once)",
                record.topic,
                record.partition,
                record.offset,
            )
            return
        KAFKA_MESSAGES_PROCESSED.inc()
        kafka_io.commit_offsets(consumer, [record])


def _install_signal_handlers(stop_event: threading.Event) -> None:
    """Route SIGTERM/SIGINT to setting ``stop_event`` so the main loop can
    stop cleanly. Only called from ``main()`` — tests never register signal
    handlers (they would hijack pytest's own Ctrl+C handling).
    """

    def _on_signal(signum, frame):  # noqa: ARG001 - signal API shape
        logger.info("received signal %d; stopping consumer loop", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)


def main() -> None:
    config = ValidationConsumerConfig.from_env()
    consumer = kafka_io.make_consumer(
        config.kafka_bootstrap_servers,
        config.topic_governance_decisions,
        "validation-consumer",
    )
    producer = kafka_io.make_producer(config.kafka_bootstrap_servers)
    logger.info("validation-consumer started, watching %s", config.topic_governance_decisions)

    stop_event = threading.Event()
    _install_signal_handlers(stop_event)
    backoff_s = 1.0
    try:
        while not stop_event.is_set():
            try:
                process_cycle(config, consumer, producer)
                backoff_s = 1.0
            except Exception:  # noqa: BLE001 - keep consuming; failures are loud in logs
                logger.exception("consumer cycle failed; retrying in %.1fs", backoff_s)
                stop_event.wait(backoff_s)
                backoff_s = min(backoff_s * 2, 30.0)
            else:
                stop_event.wait(0.1)
    finally:
        producer.flush()
        consumer.close()
        logger.info("validation-consumer stopped; producer flushed, consumer closed")


if __name__ == "__main__":
    main()
