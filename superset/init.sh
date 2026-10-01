#!/usr/bin/env bash
set -euo pipefail
superset db upgrade
python /app/pythonpath/create_admin.py
superset init
python /app/pythonpath/bootstrap_dashboard.py
