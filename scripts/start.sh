#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null || { echo 'Không tìm thấy docker. Bật Docker Desktop và WSL Integration.'; exit 1; }
docker info >/dev/null 2>&1 || { echo 'Docker chưa hoạt động. Mở Docker Desktop rồi thử lại.'; exit 1; }
test -f .env || { echo 'Chạy python3 scripts/configure.py trước.'; exit 1; }
docker compose config -q
docker compose build collector
docker compose up -d --wait superset
docker compose run --rm collector python collect_news.py
docker compose run --rm collector python verify_database.py
docker compose exec -T superset python /app/pythonpath/verify_dashboard.py
docker compose run --rm collector python export_report.py
echo 'Mở http://localhost:8088/superset/dashboard/tin-tuc-viet-nam/ trên Windows.'
echo 'Bật định kỳ: docker compose --profile scheduled up -d collector'
