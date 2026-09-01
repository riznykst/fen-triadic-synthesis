"""End-to-end smoke test for the local FEN stack (docker-compose.yml).

Publishes one EntityCandidate onto dap.entities.pending_validation.v1 and
waits for the full pipeline to complete:

    candidate -> FEN Bridge (outbound) -> mock FEN API -> webhook
              -> fen.governance.decisions.v1 -> Validation Result Consumer
              -> SPARQL UPDATE (named graph) + dap.entities.validated.v1

Checks, in order (each with retries and a timeout):
  1. readiness of Kafka, Fuseki, the webhook and the mock FEN API;
  2. the outbound consumer group is subscribed (so the candidate is not
     missed on a fresh group with auto_offset_reset=latest);
  3. a GovernanceDecision for our annotation appears on
     fen.governance.decisions.v1;
  4. the named graph carries gfen:validationStatus (any status);
  5. an EntityValidated confirmation appears on dap.entities.validated.v1.

Exits 0 on success, non-zero with a clear message on failure. Run from the
repo root against a running `docker compose up` stack (the CI job 'e2e' does
exactly this). Not part of the offline unit-test suite.
"""
from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

import requests
from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer

# Make `services` importable regardless of how the script is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.common.messages import EntityCandidate  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = "localhost:9092"
FUSEKI_PING = "http://localhost:3030/$/ping"
FUSEKI_QUERY = "http://localhost:3030/fen/query"
WEBHOOK_HEALTH = "http://localhost:8101/healthz"
MOCK_FEN_HEALTH = "http://localhost:8100/healthz"
STATUS_API_BASE = "http://localhost:8082"
STATUS_API_HEALTH = STATUS_API_BASE + "/healthz"

TOPIC_PENDING_VALIDATION = "dap.entities.pending_validation.v1"
TOPIC_GOVERNANCE_DECISIONS = "fen.governance.decisions.v1"
TOPIC_VALIDATED = "dap.entities.validated.v1"
OUTBOUND_GROUP_ID = "fen-bridge-outbound"

READY_TIMEOUT_S = 120.0
DECISION_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 1.0


def wait_for(predicate: Callable[[], bool], timeout_s: float, description: str):
    """Poll ``predicate`` every second until it is truthy or ``timeout_s``
    elapses. Probe errors are expected while the stack is starting and are
    retried; on timeout the last probe error (if any) is surfaced so the
    failure is diagnosable. Returns the last truthy probe result (callers
    use it as the checked value, e.g. the SPARQL status string).
    """
    deadline = time.monotonic() + timeout_s
    last_error: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                logger.info("%s: ready", description)
                return result
            last_error = None
        except Exception as exc:  # noqa: BLE001 - probe errors expected while starting
            last_error = exc
        time.sleep(POLL_INTERVAL_S)
    if last_error is not None:
        raise RuntimeError(
            f"timed out after {timeout_s:.0f}s waiting for {description} "
            f"(last probe error: {last_error})"
        ) from last_error
    raise RuntimeError(f"timed out after {timeout_s:.0f}s waiting for {description}")


def kafka_ready() -> bool:
    """The broker accepts TCP connections AND serves metadata for our topic —
    a bare TCP accept can happen before the broker is fully up.
    """
    host, port = KAFKA_BOOTSTRAP.split(":")
    with socket.create_connection((host, int(port)), timeout=2.0):
        pass
    producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, max_block_ms=2000)
    try:
        return producer.partitions_for(TOPIC_PENDING_VALIDATION) is not None
    finally:
        producer.close()


def http_ready(url: str) -> bool:
    resp = requests.get(url, timeout=3.0)
    return resp.status_code == 200


def outbound_group_active(admin: KafkaAdminClient) -> bool:
    """True once the outbound consumer group exists with at least one active
    member — i.e. fen-bridge-outbound is subscribed and will see our publish.

    Handles the kafka-python API drift between 2.x and 3.x:
    - 2.x: ``list_consumer_groups()`` -> list of ``(name, protocol_type)``
      tuples; ``describe_consumer_groups()`` -> {group_id: GroupDescription}.
    - 3.x: ``list_consumer_groups()`` -> [GroupOverview]; ``describe_groups()``
      -> {group_id: GroupDescription}.
    """
    list_groups_fn = getattr(admin, "list_consumer_groups", None) or getattr(admin, "list_groups", None)
    raw_groups = list_groups_fn() if list_groups_fn is not None else []
    if isinstance(raw_groups, tuple):  # defensive: (error, groups)
        raw_groups = raw_groups[1] or []
    known_ids = set()
    for g in raw_groups:
        if isinstance(g, (list, tuple)):          # 2.x tuple (name, protocol_type)
            known_ids.add(g[0])
        elif isinstance(g, dict):                 # dict shape
            known_ids.add(g.get("group_id") or g.get("group"))
        else:                                     # 3.x GroupOverview
            known_ids.add(getattr(g, "group_id", None) or getattr(g, "group", None))
    if OUTBOUND_GROUP_ID not in known_ids:
        return False
    describe_fn = getattr(admin, "describe_consumer_groups", None) or getattr(admin, "describe_groups", None)
    described = describe_fn([OUTBOUND_GROUP_ID]) if describe_fn is not None else {}
    if isinstance(described, tuple):  # defensive: (error, descriptions)
        described = described[1] or {}
    info = described.get(OUTBOUND_GROUP_ID, {})
    members = info.get("members") if isinstance(info, dict) else getattr(info, "members", None)
    return bool(members)


def wait_for_outbound_group() -> None:
    """The outbound consumer must be subscribed BEFORE we publish: it uses a
    fresh group with auto_offset_reset=latest, so a message published before
    it joins would be skipped. Uses the broker admin API; if that is
    unavailable (old tooling) we fall back to a short settle delay.
    """
    try:
        admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP)
    except Exception as exc:  # noqa: BLE001 - admin API is best-effort here
        logger.warning("admin API unavailable (%s); sleeping %ds instead", exc, 5)
        time.sleep(5)
        return
    try:
        wait_for(lambda: outbound_group_active(admin), 15, f"{OUTBOUND_GROUP_ID} consumer group")
    except Exception as exc:  # noqa: BLE001 - the admin API is flaky on some
        # kafka-python/broker combinations (e.g. kafka-python 2.3.2 against
        # Kafka 3.6 on Windows): fall back to a settle delay instead of
        # failing the whole e2e. The outbound consumer joins within seconds,
        # so a short settle preserves the "do not miss our publish" guarantee.
        logger.warning("consumer-group check failed (%s); falling back to %ds settle delay", exc, 5)
        time.sleep(5)
    finally:
        admin.close()


def make_watch_consumer(topic: str, group_id: str) -> KafkaConsumer:
    """A throwaway consumer with a fresh group and auto_offset_reset=earliest
    so messages produced just before it subscribes are still seen. Manual
    commits — this script only reads.
    """
    return KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=group_id,
        auto_offset_reset="earliest",
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        enable_auto_commit=False,
    )


def publish_candidate(producer: KafkaProducer) -> dict:
    """Publish one EntityCandidate (fields per
    schemas/kafka-events/entity-candidate.schema.json) and block on the
    delivery future so a failed send fails the script, not a later timeout.
    """
    candidate = EntityCandidate(
        annotation_id=f"smoke_{uuid.uuid4().hex[:12]}",
        document_id=f"doc_{uuid.uuid4().hex[:12]}",
        entity_label="Smoke-test entity",
        entity_type="schema:Person",
        extracted_by="smoke_test",
    ).model_dump(mode="json")
    future = producer.send(TOPIC_PENDING_VALIDATION, value=candidate)
    future.get(timeout=10.0)  # raises on delivery failure
    logger.info("published EntityCandidate %s (document %s)", candidate["annotation_id"], candidate["document_id"])
    return candidate


def wait_for_message(consumer: KafkaConsumer, topic: str, annotation_id: str, timeout_s: float) -> dict:
    """Poll ``topic`` until a message for ``annotation_id`` arrives."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        records = consumer.poll(timeout_ms=1000, max_records=50)
        for messages in records.values():
            for message in messages:
                if message.value.get("annotation_id") == annotation_id:
                    logger.info("received %s message for %s", topic, annotation_id)
                    return message.value
        time.sleep(0.2)
    raise RuntimeError(f"no {topic} message for {annotation_id} within {timeout_s:.0f}s")


def check_status_api(annotation_id: str) -> dict:
    """The web-interface layer's read API must expose the same record the
    SPARQL check just saw (Flow 2 widget data source).
    """
    resp = requests.get(f"{STATUS_API_BASE}/api/v1/status/{annotation_id}", timeout=10.0)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("found") or not body.get("validation_status"):
        raise RuntimeError(f"status-api: governance record not found for {annotation_id}")
    return body


def check_named_graph_status(annotation_id: str, document_id: str) -> str:
    """Query Fuseki for the annotation's gfen:validationStatus inside the
    document's named graph; return the status string. Raises when the triple
    is not there yet (the caller retries until the timeout).
    """
    query = f"""
PREFIX gfen: <https://w3id.org/got/fen/ontology#>
SELECT ?status WHERE {{
  GRAPH <urn:graphia:document:{document_id}:graph> {{
    <urn:graphia:annotation:{annotation_id}> gfen:validationStatus ?status .
  }}
}}
"""
    resp = requests.post(
        FUSEKI_QUERY,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=10.0,
    )
    resp.raise_for_status()
    rows = resp.json().get("results", {}).get("bindings", [])
    if not rows:
        raise RuntimeError(
            f"gfen:validationStatus not found for {annotation_id} in "
            f"urn:graphia:document:{document_id}:graph (SPARQL update has not landed)"
        )
    return rows[0]["status"]["value"]


MOCK_FEN_BASE = "http://localhost:8100"
SHAPES_PATH = str(Path(__file__).resolve().parents[1] / "docs" / "ontology" / "fen-shapes.ttl")
ONTOLOGY_PATH = str(Path(__file__).resolve().parents[1] / "docs" / "ontology" / "fen-ontology.ttl")


def mock_candidate_status(annotation_id: str) -> Optional[str]:
    """The mock FEN API's recorded status for ``annotation_id``, or None."""
    resp = requests.get(f"{MOCK_FEN_BASE}/candidates", timeout=5.0)
    resp.raise_for_status()
    for cand in resp.json().get("candidates", []):
        if cand.get("annotation_id") == annotation_id:
            return cand.get("status")
    return None


def cast_vote(annotation_id: str, outcome: str, intensity: int = 1, voter: Optional[str] = None) -> dict:
    """Cast one vote on the mock DAO (community/QV modes)."""
    payload: dict = {"outcome": outcome}
    if intensity != 1:
        payload["intensity"] = intensity
    if voter:
        payload["voter"] = voter
    resp = requests.post(f"{MOCK_FEN_BASE}/candidates/{annotation_id}/vote", json=payload, timeout=5.0)
    if resp.status_code >= 400:
        raise RuntimeError(f"vote failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()


def decide_by_votes(annotation_id: str, mode: str) -> dict:
    """Community/QV decision phase: wait for the candidate to be registered,
    cast the votes needed to reach the configured quorum/threshold, then wait
    for the mock to decide and deliver. Returns the mock's final record.
    """
    wait_for(
        lambda: mock_candidate_status(annotation_id) == "pending",
        DECISION_TIMEOUT_S,
        f"candidate {annotation_id} registered as pending (mock)",
    )
    if mode == "community":
        # quorum=2 in the CI override (docker-compose.voting.yml); cast two
        # validated votes -> majority validated.
        cast_vote(annotation_id, "validated")
        cast_vote(annotation_id, "validated")
    else:  # qv: two intensity-5 votes reach FEN_MOCK_QV_THRESHOLD=10
        cast_vote(annotation_id, "validated", intensity=5, voter="smoke_qv_a")
        cast_vote(annotation_id, "validated", intensity=5, voter="smoke_qv_b")

    def decided() -> Optional[dict]:
        record = mock_candidate_status(annotation_id)
        if record in ("validated", "disputed", "rejected"):
            return {"status": record}
        return None

    result = wait_for(decided, DECISION_TIMEOUT_S, f"{mode} decision by votes (mock)")
    logger.info("mock %s decision: %s", mode, result)
    return result


def shacl_check_named_graph(document_id: str) -> dict:
    """Fetch the document's named graph from Fuseki and validate it against
    fen-shapes.ttl (SHACL). The e2e asserts the pipeline's output conforms —
    this is the live SHACL gate for written governance provenance.
    """
    query = f"""
CONSTRUCT {{ ?s ?p ?o }} WHERE {{
  GRAPH <urn:graphia:document:{document_id}:graph> {{ ?s ?p ?o }}
}}
"""
    resp = requests.post(
        FUSEKI_QUERY, data={"query": query}, headers={"Accept": "text/turtle"}, timeout=10.0
    )
    resp.raise_for_status()
    from pyshacl import validate  # lazy: only needed for the SHACL gate

    # Merge the gfen: ontology into the data graph — sh:class checks need
    # the class/individual declarations from the ontology.
    ontology = open(ONTOLOGY_PATH, encoding="utf-8-sig").read()
    conforms, _, results_text = validate(
        ontology + "\n" + resp.text,
        shacl_graph=SHAPES_PATH,
        data_graph_format="turtle",
    )
    return {"conforms": conforms, "text": results_text}

def run(mode: str = "auto") -> None:
    """The whole smoke cycle. Raises RuntimeError on any failed step.

    ``mode`` selects how the decision is reached:
      - "auto" (default): the mock's simulated DAO decides after a delay;
      - "community" / "qv": votes are cast via POST /candidates/{id}/vote
        until the quorum/threshold is reached (mock must run with
        FEN_MOCK_VOTING=community|qv, see docker-compose.voting.yml).
    """
    wait_for(lambda: kafka_ready(), READY_TIMEOUT_S, "Kafka (localhost:9092)")
    wait_for(lambda: http_ready(FUSEKI_PING), READY_TIMEOUT_S, "Fuseki (http://localhost:3030/$/ping)")
    wait_for(lambda: http_ready(WEBHOOK_HEALTH), READY_TIMEOUT_S, "fen-bridge-webhook (http://localhost:8101/healthz)")
    wait_for(lambda: http_ready(MOCK_FEN_HEALTH), READY_TIMEOUT_S, "mock-fen-api (http://localhost:8100/healthz)")
    wait_for(lambda: http_ready(STATUS_API_HEALTH), READY_TIMEOUT_S, "status-api (http://localhost:8082/healthz)")
    wait_for_outbound_group()

    run_id = uuid.uuid4().hex[:8]
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )
    try:
        candidate = publish_candidate(producer)
        annotation_id = candidate["annotation_id"]
        document_id = candidate["document_id"]

        if mode in ("community", "qv"):
            decide_by_votes(annotation_id, mode)

        decision = wait_for_message(
            make_watch_consumer(TOPIC_GOVERNANCE_DECISIONS, f"smoke-{run_id}-decisions"),
            TOPIC_GOVERNANCE_DECISIONS,
            annotation_id,
            DECISION_TIMEOUT_S,
        )
        logger.info("governance decision %s -> %s", decision["decision_id"], decision["outcome"])

        status = wait_for(
            lambda: check_named_graph_status(annotation_id, document_id),
            DECISION_TIMEOUT_S,
            "gfen:validationStatus in named graph",
        )
        logger.info("named graph carries gfen:validationStatus=%s", status)

        status_api = wait_for(
            lambda: check_status_api(annotation_id),
            DECISION_TIMEOUT_S,
            "status-api /api/v1/status",
        )
        logger.info("status-api reports validation_status=%s", status_api["validation_status"])

        validated = wait_for_message(
            make_watch_consumer(TOPIC_VALIDATED, f"smoke-{run_id}-validated"),
            TOPIC_VALIDATED,
            annotation_id,
            DECISION_TIMEOUT_S,
        )
        logger.info("EntityValidated confirmation: %s -> %s", validated["decision_id"], validated["outcome"])

        if mode in ("community", "qv"):
            assert decision.get("quorum_reached") is True, "community/QV decision must report quorum_reached=True"
            assert decision.get("outcome") == "validated", "majority of the cast votes must win"

        shacl = shacl_check_named_graph(document_id)
        if not shacl["conforms"]:
            raise RuntimeError(f"SHACL validation of the named graph FAILED:\n{shacl['text']}")
        logger.info("SHACL: named graph conforms to fen-shapes.ttl")
    finally:
        producer.close()

    logger.info("E2E SMOKE TEST PASSED (%s mode): %s", mode, annotation_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="FEN end-to-end smoke test")
    parser.add_argument(
        "--mode",
        choices=("auto", "community", "qv"),
        default="auto",
        help="decision mode to exercise (auto = mock decides after a delay; "
        "community/qv = cast votes via POST /candidates/{id}/vote; the mock "
        "must run with FEN_MOCK_VOTING set accordingly, see "
        "docker-compose.voting.yml)",
    )
    args = parser.parse_args()
    try:
        run(mode=args.mode)
        return 0
    except Exception as exc:  # noqa: BLE001 - any failed step is a failed smoke test
        logger.error("E2E SMOKE TEST FAILED (%s mode): %s", args.mode, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
