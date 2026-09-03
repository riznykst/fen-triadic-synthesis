"""FEN Bridge — outbound process.

Consumes dap.entities.pending_validation.v1 (produced by the existing WP4
Entity & Relation Extraction service, unchanged) and forwards batches to the
external FEN API for Agentic Scaffolding + DAO review.

Runs as the `fen-bridge-outbound` container (see docker-compose.yml). Does
NOT wait for a governance decision here — that arrives asynchronously via
webhook.py and a separate topic. This process never blocks the pipeline.

Delivery guarantee (at-least-once): offsets are committed ONLY after the
whole batch was accepted by the FEN API (commit-after-processing). If the
forward fails, the batch is left uncommitted and is redelivered — a candidate
that never reaches FEN simply stays ``gfen:pending`` and will be retried.
"""
from __future__ import annotations

import logging
import os
import signal
import threading
import time

from services.common.logging_config import log_level_from_env, setup_logging
from services.common.metrics import KAFKA_MESSAGES_FAILED, KAFKA_MESSAGES_PROCESSED
from services.fen_bridge.config import FenBridgeConfig
from services.fen_bridge.fen_client import FenClient
from prometheus_client import start_http_server

from services.fen_bridge.kafka_io import commit_offsets, make_consumer, poll_batch_with_offsets

setup_logging("fen-bridge-outbound", level=log_level_from_env())
logger = logging.getLogger(__name__)


def run(config: FenBridgeConfig, client: FenClient, consumer) -> None:
    """Single poll-forward cycle, factored out for testability. Runs once;
    `main()` below loops it forever.

    Commits the batch's offsets only when ``submit_candidates`` returned True
    (the FEN API accepted it); on False the offsets stay uncommitted so the
    batch is redelivered — at-least-once, never at-most-once.
    """
    batch = list(poll_batch_with_offsets(consumer, config.batch_size, config.poll_timeout_ms))
    if not batch:
        return
    if client.submit_candidates([record.value for record in batch]):
        # Per-record commit (offset+1 for every record in the batch), NOT the
        # whole-consumer position: a future change to poll caps or batch
        # truncation must never commit records that were fetched but not
        # forwarded (that would silently downgrade at-least-once to
        # at-most-once). Same contract as validation-consumer (TECH-DEBT P0).
        commit_offsets(consumer, batch)
        KAFKA_MESSAGES_PROCESSED.inc(len(batch))
        logger.info("committed %d message(s) after successful forward", len(batch))
    else:
        KAFKA_MESSAGES_FAILED.inc(len(batch))
        logger.warning(
            "FEN API did not accept the batch (%d message(s)); offsets NOT committed — "
            "the batch will be redelivered (at-least-once)",
            len(batch),
        )


def _install_signal_handlers(stop_event: threading.Event) -> None:
    """Route SIGTERM/SIGINT to setting ``stop_event`` so the main loop can
    stop cleanly. Only called from ``main()`` — tests never register signal
    handlers (they would hijack pytest's own Ctrl+C handling).
    """

    def _on_signal(signum, frame):  # noqa: ARG001 - signal API shape
        logger.info("received signal %d; stopping outbound loop", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)


def main() -> None:
    config = FenBridgeConfig.from_env()
    # Expose Prometheus metrics on a dedicated port (scraped by the local
    # prometheus service, see monitoring/prometheus.yml). Only inside main()
    # — imports must never start a server (tests stay offline).
    start_http_server(int(os.getenv("METRICS_PORT", "9101")))
    client = FenClient(config.fen_api_base_url)
    consumer = make_consumer(
        config.kafka_bootstrap_servers,
        config.topic_pending_validation,
        config.consumer_group_id,
    )
    logger.info("fen-bridge-outbound started, watching %s", config.topic_pending_validation)

    stop_event = threading.Event()
    _install_signal_handlers(stop_event)
    backoff_s = 1.0
    try:
        while not stop_event.is_set():
            try:
                run(config, client, consumer)
                backoff_s = 1.0
            except Exception:  # noqa: BLE001 - keep the loop alive across broker blips
                logger.exception("outbound cycle failed; retrying in %.1fs", backoff_s)
                stop_event.wait(backoff_s)
                backoff_s = min(backoff_s * 2, 30.0)
            else:
                stop_event.wait(0.1)
    finally:
        consumer.close()
        logger.info("fen-bridge-outbound stopped; consumer closed")


if __name__ == "__main__":
    main()
