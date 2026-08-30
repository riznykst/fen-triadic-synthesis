# Prometheus with the repo's config baked in.
#
# Configs are baked into the image (rather than bind-mounted) so the stack
# works everywhere: Docker Desktop on Windows cannot reliably share files
# from removable drives (SD cards are not registered in WSL's drvfs), and
# single-file bind mounts break under gRPC-FUSE. Baking also keeps CI
# self-hosted runs identical to local dev.
#
# Rebuild after editing monitoring/prometheus/prometheus.yml:
#   docker compose build prometheus && docker compose up -d prometheus
FROM prom/prometheus:v2.53.0
COPY prometheus/prometheus.yml /etc/prometheus/prometheus.yml