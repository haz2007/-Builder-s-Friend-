#!/usr/bin/env bash
# Бэкап базы и фото товаров:
#   scripts/backup.sh
# Файлы кладутся в backups/ (рядом с проектом), старше BACKUP_KEEP_DAYS дней удаляются.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP="${BACKUP_PREFIX:-}$(date +%F_%H%M%S)"

cd "$PROJECT_DIR"
ENV_FILE="${ENV_FILE:-.env.production}"
set -a; source "$ENV_FILE"; set +a
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE")
DB_USER="${POSTGRES_USER:-wood}"
DB_NAME="${POSTGRES_DB:-wood_commerce}"

mkdir -p "$BACKUP_DIR"

# База: сжатый формат pg_dump, восстанавливается scripts/restore.sh
DB_FILE="$BACKUP_DIR/db_$STAMP.dump"
"${COMPOSE[@]}" exec -T db pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$DB_FILE.tmp"
mv "$DB_FILE.tmp" "$DB_FILE"

# Фото товаров из тома uploads
UPLOADS_FILE="$BACKUP_DIR/uploads_$STAMP.tar.gz"
"${COMPOSE[@]}" exec -T backend tar -czf - -C /app uploads > "$UPLOADS_FILE"

find "$BACKUP_DIR" -name '*db_*.dump' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'uploads_*.tar.gz' -mtime +"$KEEP_DAYS" -delete

echo "$(date '+%F %T') бэкап готов: $(basename "$DB_FILE") ($(du -h "$DB_FILE" | cut -f1)), $(basename "$UPLOADS_FILE")"
