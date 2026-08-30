# Grafana with provisioning (datasources + dashboards) baked in.
# Same rationale as monitoring/docker/prometheus.Dockerfile: no host
# bind-mount dependency (Windows + removable drive file sharing is broken).
# Rebuild after editing monitoring/grafana/*:
#   docker compose build grafana && docker compose up -d grafana
FROM grafana/grafana:11.1.0
COPY grafana/provisioning /etc/grafana/provisioning
COPY grafana/dashboards /var/lib/grafana/dashboards