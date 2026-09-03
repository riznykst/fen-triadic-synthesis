"""Renders k8s/configmap.yaml from k8s/env-shared.yaml — the single source
of the shared environment (TECH-DEBT P3: no more hand-editing two copies
that can drift).

docker-compose.yml stays the source for its own values (listener addresses,
dev credentials); the TOPIC_* names are shared and asserted end to end by
the CI e2e smoke, so drift would break CI loudly.

Usage:
    python scripts/generate_k8s_configmap.py     # rewrites k8s/configmap.yaml

Freshness is enforced by tests/test_k8s_configmap.py (regenerates in memory
and compares) — commit the regenerated file together with env-shared.yaml.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "k8s" / "env-shared.yaml"
OUTPUT = ROOT / "k8s" / "configmap.yaml"

HEADER = """\
# Shared environment for the four FEN application deployments. Kafka and
# the RDF store (Virtuoso in production, Fuseki in local dev) are EXTERNAL
# to this deployment — see docs/architecture.md, "Kubernetes / OKD
# deployment". Values below are placeholders; replace before deploying.
# GENERATED from k8s/env-shared.yaml by scripts/generate_k8s_configmap.py —
# edit the SOURCE file, then run the generator (freshness is enforced by
# tests/test_k8s_configmap.py).
apiVersion: v1
kind: ConfigMap
metadata:
  name: fen-config
  labels:
    app.kubernetes.io/part-of: fen-triadic-synthesis
data:
"""


def render() -> str:
    """The full configmap.yaml text for the current env-shared.yaml."""
    return HEADER + SOURCE.read_text(encoding="utf-8")


def main() -> None:
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT} from {SOURCE}")


if __name__ == "__main__":
    sys.exit(main())
