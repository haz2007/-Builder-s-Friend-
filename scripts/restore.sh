#!/usr/bin/env bash
# Восстановление базы из бэкапа (текущие данные будут заменены!):
#   scripts/restore.sh backups/db_2026-10-20_0330.dump
#   scripts/restore.sh backups/db_2026-10-20_0330.dump backups/uploads_2026-10-20_0330.tar.gz
set -euo pipefail

DB_FILE="${1:?Укажи файл бэкапа базы: scripts/restore.sh backups/db_....dump}"
UPLOADS_FILE="${2:-}"
[[ -f "$DB_FILE" ]] || { echo "Нет файла $DB_FILE" >&2; exit 1; }

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_FILE="$(cd "$(dirname "$DB_FILE")" && pwd)/$(basename "$DB_FILE")"
[[ -z "$UPLOADS_FILE" ]] || UPLOADS_FILE="$(cd "$(dirname "$UPLOADS_FILE")" && pwd)/$(basename "$UPLOADS_FILE")"

cd "$PROJECT_DIR"
ENV_FILE="${ENV_FILE:-.env.production}"
set -a; source "$ENV_FILE"; set +a
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE")
DB_USER="${POSTGRES_USER:-wood}"
DB_NAME="${POSTGRES_DB:-wood_commerce}"

read -r -p "База $DB_NAME будет заменена данными из $(basename "$DB_FILE"). Продолжить? [y/N] " answer
[[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Отменено"; exit 0; }

# Перед заменой — свежий бэкап текущего состояния, на всякий случай
BACKUP_PREFIX=before-restore_ "$PROJECT_DIR/scripts/backup.sh"

# Останавливаем всё, что пишет в базу
"${COMPOSE[@]}" --profile bot stop backend bot

"${COMPOSE[@]}" exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner < "$DB_FILE"

if [[ -n "$UPLOADS_FILE" ]]; then
  "${COMPOSE[@]}" run --rm -T --no-deps --entrypoint "" backend \
    sh -c 'rm -rf /app/uploads/* && tar -xzf - -C /app' < "$UPLOADS_FILE"
fi

"${COMPOSE[@]}" --profile bot start backend bot 2>/dev/null || "${COMPOSE[@]}" start backend
echo "Готово: база восстановлена из $(basename "$DB_FILE")"
