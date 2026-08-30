# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (research MVP) | ✔ research/prototype use only |

This is a **research prototype**, not a production system (see the
[Status](https://github.com/riznykst/fen-triadic-synthesis#status) section of
the README). Security hardening for production deployment is explicitly out
of scope for the current phase.

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

- Email: [riznykv@gmx.de](mailto:riznykv@gmx.de) with the subject
  `[FEN-SECURITY] ...`
- Include: affected version/commit, a minimal reproduction, and your suggested
  fix if you have one.
- You will receive an acknowledgement within 7 days and a status update
  (accepted / rejected / timeline) within 14 days.

## Known security posture (current phase)

- **Webhook auth:** `FEN_WEBHOOK_TOKEN` bearer-token check is implemented;
  it **must** be set for any non-local deployment (see `.env.example`).
- **Secrets:** no secrets are tracked in the repository; k8s `Secret`
  manifests are placeholders.
- **CORS:** the Status API defaults to `*` for local dev — restrict
  `FEN_CORS_ORIGINS` in any exposed deployment.
- **LLM judge:** decision-support only (ADR-004) — never writes
  `gfen:validationStatus`; runs only inside the demo mock.
- **Kafka:** at-least-once with idempotent producer and commit-after-
  processing; transport TLS and ACLs are production items (see
  `docs/integration-verification-plan.md`).
- **Input validation:** Pydantic contracts for message schemas
  (`services/common/messages.py`), SHACL validation at the Scaffold phase,
  XSS-escaping in the web layer.