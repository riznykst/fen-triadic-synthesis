# Promtail with the repo's config baked in.
# Same rationale as monitoring/docker/prometheus.Dockerfile: no host
# bind-mount dependency (Windows + removable drive file sharing is broken).
# Rebuild after editing monitoring/promtail/promtail.yml:
#   docker compose build promtail && docker compose up -d promtail
FROM grafana/promtail:3.2.2
# The base image (Ubuntu 24.04) has no wget, but the compose healthcheck
# probes http://localhost:9080/ready with wget - install it explicitly.
RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*
COPY promtail/promtail.yml /etc/promtail/config.yml
