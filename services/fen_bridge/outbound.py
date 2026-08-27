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
import time

from services.fen_bridge.config import FenBridgeConfig
from services.fen_bridge.fen_client import FenClient
from services.fen_bridge.kafka_io import make_consumer, poll_batch_with_offsets

logging.basicConfig(level=logging.INFO)
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
        consumer.commit()
        logger.info("committed %d message(s) after successful forward", len(batch))
    else:
        logger.warning(
            "FEN API did not accept the batch (%d message(s)); offsets NOT committed — "
            "the batch will be redelivered (at-least-once)",
            len(batch),
        )


def main() -> None:
    config = FenBridgeConfig.from_env()
    client = FenClient(config.fen_api_base_url)
    consumer = make_consumer(
        config.kafka_bootstrap_servers,
        config.topic_pending_validation,
        config.consumer_group_id,
    )
    logger.info("fen-bridge-outbound started, watching %s", config.topic_pending_validation)

    backoff_s = 1.0
    while True:
        try:
            run(config, client, consumer)
            backoff_s = 1.0
        except Exception:  # noqa: BLE001 - keep the loop alive across broker blips
            logger.exception("outbound cycle failed; retrying in %.1fs", backoff_s)
            time.sleep(backoff_s)
            backoff_s = min(backoff_s * 2, 30.0)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
