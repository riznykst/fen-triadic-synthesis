# One Dockerfile for every FEN Python service (TECH-DEBT P1 consolidation).
# A single `deps` stage installs the UNION of service requirements in one
# pip layer (docker/requirements-service.txt), then thin targets add only
# the source trees each process needs. docker-compose.yml selects the
# target via build.target. Rebuild all: docker compose build.
FROM python:3.11.9-slim-bookworm AS deps
WORKDIR /app
COPY docker/requirements-service.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# --- fen-bridge-outbound ---------------------------------------------------
FROM deps AS outbound
COPY services /app/services
CMD ["python", "-m", "services.fen_bridge.outbound"]

# --- fen-bridge-webhook ----------------------------------------------------
FROM deps AS webhook
COPY services /app/services
EXPOSE 8101
CMD ["uvicorn", "services.fen_bridge.webhook:app", "--host", "0.0.0.0", "--port", "8101"]

# --- validation-consumer ----------------------------------------------------
FROM deps AS consumer
COPY services /app/services
CMD ["python", "-m", "services.validation_consumer.main"]

# --- mock-fen-api (demo DAO, ADR-002 stand-in) ------------------------------
FROM deps AS mock
COPY mock_fen_api /app/mock_fen_api
COPY services /app/services
EXPOSE 8100
CMD ["uvicorn", "mock_fen_api.main:app", "--host", "0.0.0.0", "--port", "8100"]

# --- status-api (read side + static web) ------------------------------------
FROM deps AS status-api
COPY services /app/services
COPY web /app/web
EXPOSE 8082
CMD ["uvicorn", "services.status_api.main:app", "--host", "0.0.0.0", "--port", "8082"]
