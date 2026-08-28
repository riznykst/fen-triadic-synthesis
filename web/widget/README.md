# FEN status widget (Flow 2) — embeddable validation-status badge

A zero-build Web Component that shows the community-validation status of any
entity in the SSH KG: `gfen:validationStatus` (validated / disputed /
rejected / pending / unknown), resolved **live** from the RDF store through
the Status API.

## Usage

```html
<script src="fen-status-widget.js"></script>
<fen-status annotation-id="annotation_a1" api-base="http://localhost:8082"></fen-status>
```

| Attribute | Required | Default | Description |
|---|---|---|---|
| `annotation-id` | yes | — | `oa:Annotation` id, e.g. `annotation_a1` |
| `api-base` | no | `http://localhost:8082` | Status API origin |
| `theme` | no | `dark` | `dark` or `light` |

Clicking the badge expands decision details: validation method,
dereferenceable PID (`w3id.org/fen/id/decision/...`, ADR-003), reputation
snapshot and the on-chain ledger anchor (hash only, ADR-001).

## How it works

- Widget → `GET {api-base}/api/v1/status/{annotation-id}` (contract in
  [`web/api.md`](../api.md)).
- The Status API executes a SPARQL SELECT over the named graphs (Fuseki
  locally, Virtuoso in production) — the widget never talks to Kafka or the
  graph directly and never writes anything.
- CORS is enabled on the Status API so the widget can be embedded in
  third-party pages (GoTriple, dataset portals).

## Run locally

```bash
docker compose up --build status-api    # serves /web/demo.html at :8082
# or open web/widget/demo.html directly (widget fetches :8082)
```
