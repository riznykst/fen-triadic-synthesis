# Promtail with the repo's config baked in.
# Same rationale as monitoring/docker/prometheus.Dockerfile: no host
# bind-mount dependency (Windows + removable drive file sharing is broken).
# Rebuild after editing monitoring/promtail/promtail.yml:
#   docker compose build promtail && docker compose up -d promtail
FROM grafana/promtail:3.2.2
COPY promtail/promtail.yml /etc/promtail/config.yml