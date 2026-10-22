#!/usr/bin/env bash
# Удаление данных с истёкшим сроком хранения (152-ФЗ), раз в сутки по cron:
#   scripts/purge-expired.sh
# Что и через сколько удаляется — backend/app/services/retention.py.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
ENV_FILE="${ENV_FILE:-.env.production}"

echo "$(date '+%F %T') $(docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" exec -T backend python manage.py purge-expired)"
