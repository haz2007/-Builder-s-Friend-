#!/usr/bin/env bash
# Мониторинг сервера: запускается cron каждые 5 минут (scripts/setup-server.sh).
#   scripts/healthcheck.sh            — проверить и при проблеме написать в Telegram
#   HEALTHCHECK_DRY_RUN=1 scripts/healthcheck.sh — только напечатать, ничего не отправлять
#
# Проверяет: API и базу, контейнеры, место на диске, свежесть бэкапа и его копии на Диске,
# застрявшие сообщения Telegram. Пишет владельцу магазина в Telegram один раз
# при поломке и один раз, когда всё восстановилось (без спама каждые 5 минут).
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
ENV_FILE="${ENV_FILE:-.env.production}"
[[ -f "$ENV_FILE" ]] && { set -a; source "$ENV_FILE"; set +a; }
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE")

# С доменом Caddy отвечает только по HTTPS и только на этот домен (на
# http://localhost — перенаправление), поэтому проверяем настоящий адрес сайта,
# но через сам сервер (--resolve), не завися от внешнего DNS. Без домена — :80.
SITE_HOST="${SITE_ADDRESS:-}"
SITE_HOST="${SITE_HOST#*://}"
SITE_HOST="${SITE_HOST%%[/ ,]*}"
if [[ -n "$SITE_HOST" && "$SITE_HOST" != :* ]]; then
  HEALTH_URL="${HEALTH_URL:-https://$SITE_HOST/api/v1/health}"
  CURL_RESOLVE=(--resolve "$SITE_HOST:${HTTPS_PORT:-443}:127.0.0.1")
else
  HEALTH_URL="${HEALTH_URL:-http://localhost:${HTTP_PORT:-80}/api/v1/health}"
  CURL_RESOLVE=()
fi
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
STATE_FILE="${STATE_FILE:-$PROJECT_DIR/.healthcheck_state}"
DISK_LIMIT="${DISK_LIMIT:-90}"   # % занятого места
problems=()

# 1. API и база
health="$(curl -fsS -m 10 "${CURL_RESOLVE[@]}" "$HEALTH_URL" 2>/dev/null)"
if [[ -z "$health" ]]; then
  problems+=("сайт или API не отвечают ($HEALTH_URL)")
else
  read -r stuck failed < <(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("outbox_stuck",0), d.get("outbox_failed",0))' <<<"$health")
  [[ "${stuck:-0}" -gt 0 ]] && problems+=("в Telegram не уходят сообщения: $stuck ждут дольше 10 минут")
  [[ "${failed:-0}" -gt 0 ]] && problems+=("$failed сообщений в Telegram так и не отправлены")
fi

# 2. Контейнеры
if command -v docker >/dev/null; then
  for service in db backend web; do
    state="$("${COMPOSE[@]}" ps --format '{{.State}}' "$service" 2>/dev/null | head -1)"
    [[ "$state" != "running" ]] && problems+=("контейнер $service: ${state:-не запущен}")
  done
  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    state="$("${COMPOSE[@]}" --profile bot ps --format '{{.State}}' bot 2>/dev/null | head -1)"
    [[ "$state" != "running" ]] && problems+=("Telegram-бот: ${state:-не запущен}")
  fi
fi

# 3. Диск
used="$(df -P / | awk 'NR==2 {gsub("%", "", $5); print $5}')"
[[ "${used:-0}" -ge "$DISK_LIMIT" ]] && problems+=("диск заполнен на ${used}%")

# 4. Бэкап не старше суток (с запасом)
if [[ -d "$BACKUP_DIR" ]] && [[ -z "$(find "$BACKUP_DIR" -name '*db_*.dump' -mmin -1560 2>/dev/null | head -1)" ]]; then
  problems+=("нет свежего бэкапа базы за последние сутки")
fi

# 5. Копия на Яндекс Диске не старше суток — если выгрузка настроена
OFFSITE_CREDS="${OFFSITE_TOKEN:-/root/.config/builders-friend/yandex-disk.token}"
if [[ -f "$OFFSITE_CREDS" && -n "$(find "$BACKUP_DIR" -name '*db_*.dump' 2>/dev/null | head -1)" ]]; then
  last_offsite="$(cat "$BACKUP_DIR/.offsite_ok" 2>/dev/null || echo 0)"
  if (( $(date +%s) - last_offsite > 1560 * 60 )); then
    problems+=("копия бэкапа не ушла на Яндекс Диск за последние сутки")
  fi
fi

# --- куда писать: MONITOR_CHAT_ID или владелец магазина, вошедший в бота
chat_id="${MONITOR_CHAT_ID:-}"
if [[ -z "$chat_id" ]] && command -v docker >/dev/null; then
  chat_id="$("${COMPOSE[@]}" exec -T db psql -U "${POSTGRES_USER:-wood}" -d "${POSTGRES_DB:-wood_commerce}" -tAc \
    "SELECT l.telegram_chat_id FROM telegram_account_links l JOIN users u ON u.id = l.user_id
     WHERE u.is_owner = 1 LIMIT 1" 2>/dev/null | tr -d '[:space:]')"
fi

notify() {
  local text="$1"
  if [[ -n "${HEALTHCHECK_DRY_RUN:-}" || -z "${TELEGRAM_BOT_TOKEN:-}" || -z "$chat_id" ]]; then
    echo "$text"
    return
  fi
  local api="${TELEGRAM_API_URL:-https://api.telegram.org}"
  curl -fsS -m 15 ${TELEGRAM_PROXY:+--proxy "$TELEGRAM_PROXY"} \
    "${api%/}/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=$chat_id" --data-urlencode "text=$text" >/dev/null || echo "$text"
}

previous="$(cat "$STATE_FILE" 2>/dev/null || echo ok)"
if (( ${#problems[@]} )); then
  current="$(printf '%s\n' "${problems[@]}")"
  # Пишем, только если поломка новая или изменилась
  if [[ "$current" != "$previous" ]]; then
    notify "⚠️ Друг Строителя — проблема на сервере:
$(printf '• %s\n' "${problems[@]}")"
    printf '%s' "$current" > "$STATE_FILE"
  fi
  exit 1
fi

if [[ "$previous" != "ok" ]]; then
  notify "✅ Друг Строителя — всё снова работает."
fi
echo ok > "$STATE_FILE"
