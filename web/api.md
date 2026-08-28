# FEN Web Interface — REST contract (v1)

The web-interface layer (widget + portal) talks only to HTTP APIs. In local
dev the **mock FEN API** (`mock_fen_api`, port 8100) and the **Status API**
(`services/status_api`, port 8082) implement this contract; in production the
real FEN backend (Agentic Scaffolding + DAO, external per ADR-002) must
implement the *same* contract — that is what keeps the UI backend-agnostic.

## Base URLs

| Service | Local dev | Production |
|---|---|---|
| DAO / candidates API | `http://localhost:8100` (mock) | real FEN backend (TBD with consortium) |
| Status API (read) | `http://localhost:8082` | federation-node read endpoint |

Both enable CORS (`FEN_CORS_ORIGINS`, default `*`) so the widget can be
embedded cross-origin.

## 1. Submit candidates — `POST /candidates`

Body (same shape as the Kafka contract `EntityCandidate`):

```json
{ "candidates": [ { "annotation_id": "annotation_a1", "document_id": "d12345", "entity_label": "Sokolowizna", "entity_type": "schema:DefinedTerm" } ] }
```

→ `200 {"accepted": 1}`. Candidates are published with `gfen:pending` and the
pipeline never blocks (D2.2 §4.1).

## 2. List candidates — `GET /candidates`

→ `200 {"candidates": [ {annotation_id, document_id, entity_label, status,
votes, quorum: {votes, required, reached}, decision}]}`

`status`: `pending` | `deciding` | `validated` | `disputed` | `rejected`.

## 3. Cast a community vote — `POST /candidates/{annotation_id}/vote`

```json
{ "outcome": "validated" }
```

- `200` — vote recorded: `{"votes": {...}, "quorum": {votes, required, reached}}`;
  when the quorum is reached the response also carries
  `{"outcome": "<majority>", "note": "quorum reached — decision being delivered"}`.
- `404` — unknown annotation id.
- `409` — community voting disabled (`FEN_MOCK_VOTING=auto`) or candidate already decided.
- `422` — `outcome` not in `validated | disputed | rejected`.

> Real Quadratic Voting is external (ADR-002); this endpoint is the demo
> implementation of the same interface. The LLM judge is decision-support
> only and never counts as a vote (ADR-004).

## 4. Validation status (read, widget) — `GET /api/v1/status/{annotation_id}`

Resolved live from the RDF store via SPARQL (named graphs):

- `200` — `{"annotation_id", "found": true, "validation_status",
  "validation_method", "governance_decision_id", "reputation_snapshot",
  "ledger_anchor", "provenance": [...]}` — values are the `gfen:` URIs,
  status as short fragment (`validated`, …).
- `200 {"found": false, "validation_status": "unknown"}` — no governance
  record yet (never extracted or still pending without gfen: triples).
- `503` — RDF store unreachable.

## Notes

- All endpoints are JSON; errors use FastAPI's default `{"detail": ...}`.
- Auth: the webhook (`POST /webhook/decision`) is a *server-to-server*
  callback and requires `FEN_WEBHOOK_TOKEN` outside dev; the read/vote APIs
  are unauthenticated in the demo — production adds OIDC/DAO identity.
- Versioning: contract version `v1`; breaking changes bump the path.
