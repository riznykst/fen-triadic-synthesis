"""Regenerates schemas/kafka-events/*.schema.json from
services/common/messages.py — the models are the single source of truth,
never hand-edit the generated JSON (AGENT_PLAN.md, Phase 1).

Usage:
    python scripts/generate_schemas.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make `services` importable regardless of how the script is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.common.messages import EntityCandidate, EntityValidated, GovernanceDecision  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "schemas" / "kafka-events"

MODELS = {
    "entity-candidate": EntityCandidate,
    "governance-decision": GovernanceDecision,
    "entity-validated": EntityValidated,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        path = OUT_DIR / f"{name}.schema.json"
        schema = model.model_json_schema()
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
