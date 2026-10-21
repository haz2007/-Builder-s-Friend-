#!/usr/bin/env bash
# Копия последнего бэкапа на Яндекс Диск: если сервер пропадёт целиком,
# база и фото останутся. Запускается в конце scripts/backup.sh.
#   scripts/offsite-backup.sh
#
# На Диске — папка builders-friend-backups/ с 7 копиями по дням недели
# (db_1.dump … db_7.dump): каждая перезаписывается через неделю, место не растёт.
# REST API Диска (WebDAV на бесплатном тарифе закрыт); токен —
# scripts/set-offsite-credentials.sh.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
TOKEN_FILE="${OFFSITE_TOKEN:-/root/.config/builders-friend/yandex-disk.token}"
API="https://cloud-api.yandex.net/v1/disk/resources"
FOLDER="disk:/builders-friend-backups"

if [[ ! -f "$TOKEN_FILE" ]]; then
  echo "Выгрузка на Диск не настроена: нет $TOKEN_FILE (scripts/set-offsite-credentials.sh)"
  exit 0
fi

latest() { ls -1t "$BACKUP_DIR"/$1 2>/dev/null | head -1; }
DB_FILE="$(latest 'db_*.dump')"
UPLOADS_FILE="$(latest 'uploads_*.tar.gz')"
if [[ -z "$DB_FILE" ]]; then
  echo "Нечего выгружать: в $BACKUP_DIR нет бэкапа базы" >&2
  exit 1
fi

DAY="$(date +%u)"   # 1 — понедельник … 7 — воскресенье
api() { curl -sS -m 600 -H @"$TOKEN_FILE" "$@"; }
json_field() { python3 -c "import json,sys; print(json.load(sys.stdin).get('$1', ''))"; }

# Папку создаём один раз; «уже есть» (409) — не ошибка
api -X PUT -o /dev/null "$API?path=$FOLDER" || true

upload() {
  local file="$1" name="$2" href size remote_size
  # 1) Диск выдаёт адрес для загрузки, 2) файл кладётся по этому адресу
  href="$(api "$API/upload?path=$FOLDER/$name&overwrite=true" | json_field href)"
  if [[ -z "$href" ]]; then
    echo "Диск не выдал адрес для загрузки $name (истёк токен?)" >&2
    return 1
  fi
  curl -fsS -m 600 -T "$file" "$href" -o /dev/null
  # Проверяем, что на Диске файл того же размера, — иначе это не копия
  size="$(stat -c %s "$file")"
  remote_size="$(api "$API?path=$FOLDER/$name&fields=size" | json_field size)"
  if [[ "$size" != "$remote_size" ]]; then
    echo "Размер на Диске не совпал для $name: ${remote_size:-?} вместо $size" >&2
    return 1
  fi
}

upload "$DB_FILE" "db_$DAY.dump"
[[ -n "$UPLOADS_FILE" ]] && upload "$UPLOADS_FILE" "uploads_$DAY.tar.gz"

# Для мониторинга: когда в последний раз копия ушла на Диск
date +%s > "$BACKUP_DIR/.offsite_ok"
echo "$(date '+%F %T') копия на Яндекс Диске: db_$DAY.dump$([[ -n "$UPLOADS_FILE" ]] && echo ", uploads_$DAY.tar.gz")"
