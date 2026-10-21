#!/usr/bin/env bash
# Один раз: токен Яндекс Диска для выгрузки бэкапов.
#   sudo bash scripts/set-offsite-credentials.sh
#
# Бесплатный Диск не пускает по WebDAV, поэтому — REST API с OAuth-токеном.
# Как получить токен — DEPLOY.md, раздел «Копия бэкапов на Яндекс Диске».
# Токен хранится в /root/.config/builders-friend/yandex-disk.token (права 600):
# не в проекте и не в git. Отозвать — на id.yandex.ru → «Данные» → «Доступы».
set -euo pipefail

CREDS_DIR=/root/.config/builders-friend
TOKEN_FILE="$CREDS_DIR/yandex-disk.token"

read -rsp "OAuth-токен Яндекс Диска (не отображается): " token
echo
token="$(printf '%s' "$token" | tr -d '[:space:]')"
if [[ -z "$token" ]]; then
  echo "Токен пустой" >&2
  exit 1
fi

mkdir -p "$CREDS_DIR"
chmod 700 "$CREDS_DIR"
umask 077
printf 'Authorization: OAuth %s\n' "$token" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"
unset token

# Заголовок читается из файла (-H @файл): токена нет в командной строке
code="$(curl -sS -o /dev/null -w '%{http_code}' -m 20 -H @"$TOKEN_FILE" https://cloud-api.yandex.net/v1/disk/ || true)"
if [[ "$code" == "200" ]]; then
  echo "Готово: Яндекс Диск принял токен."
else
  rm -f "$TOKEN_FILE"
  echo "Яндекс Диск не принял токен (код $code). Ничего не сохранено, попробуйте ещё раз." >&2
  exit 1
fi
