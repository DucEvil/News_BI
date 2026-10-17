#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker info >/dev/null
test -f .env || { echo 'Create .env first.'; exit 1; }
python3 scripts/configure.py --add-ai
docker compose --profile ai build analytics
docker compose up -d --wait --no-deps postgres
if ! docker compose exec -T postgres psql -U news -d superset_meta -Atc "SELECT count(*) FROM dashboards WHERE slug='tin-tuc-viet-nam'" | grep -qx 1; then
  docker compose run --rm superset-init
fi
docker compose up -d --wait --no-deps superset
credential_args=()
if [[ "${1:-}" == '--sync-admin-password' ]]; then
  credential_args+=(--sync-password)
fi
docker compose exec -T superset python /app/pythonpath/check_admin_credentials.py "${credential_args[@]}"
docker compose --profile ai run --rm analytics python -m analytics.pipeline
docker compose --profile ai run --rm analytics python -m analytics.verify_mcp
echo 'TH2: http://localhost:8088/superset/dashboard/tin-tuc-ai-th2/'
echo 'Schedule (optional): docker compose --profile ai up -d ai-worker'
