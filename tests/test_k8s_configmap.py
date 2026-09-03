"""Freshness guard for the k8s ConfigMap (TECH-DEBT P3 single env source).

k8s/configmap.yaml is GENERATED from k8s/env-shared.yaml by
scripts/generate_k8s_configmap.py — this test regenerates it in memory and
compares, so editing env-shared.yaml without committing the regenerated
configmap fails the suite with a clear instruction.
"""
from __future__ import annotations

from scripts.generate_k8s_configmap import OUTPUT, render


def test_k8s_configmap_matches_env_shared_source():
    assert OUTPUT.exists(), f"missing generated file {OUTPUT}"
    committed = OUTPUT.read_text(encoding="utf-8")
    fresh = render()
    assert committed == fresh, (
        "k8s/configmap.yaml is STALE — k8s/env-shared.yaml changed. "
        "Run `python scripts/generate_k8s_configmap.py` and commit the result"
    )
    assert "GENERATED from k8s/env-shared.yaml" in committed


def test_env_shared_contains_required_keys():
    source = (OUTPUT.parent / "env-shared.yaml").read_text(encoding="utf-8")
    for key in (
        "KAFKA_BOOTSTRAP_SERVERS",
        "TOPIC_PENDING_VALIDATION",
        "TOPIC_GOVERNANCE_DECISIONS",
        "TOPIC_VALIDATED",
        "FEN_API_BASE_URL",
        "SPARQL_UPDATE_ENDPOINT",
        "SPARQL_QUERY_ENDPOINT",
        "SPARQL_PING_ENDPOINT",
        "FEN_NAAN",
        "FEN_CORS_ORIGINS",
        "FEN_WEB_DIR",
    ):
        assert key in source, f"k8s/env-shared.yaml missing {key}"
