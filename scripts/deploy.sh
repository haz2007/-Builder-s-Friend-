#!/usr/bin/env bash
# Выкатка новой версии: GitHub Actions после зелёного CI присылает архив кода по SSH.
#   git archive --format=tar HEAD | ssh root@сервер     (ключ CI запускает только этот скрипт)
#
# В /root/.ssh/authorized_keys ключ CI ограничен этим скриптом:
#   restrict,command="/opt/builders-friend/scripts/deploy.sh" ssh-ed25519 AAAA… github-actions-deploy
#
# Что делает: бэкап базы → распаковка кода поверх /opt/builders-friend → пересборка
# контейнеров (миграции применяет сам backend при старте) → проверка, что API отвечает.
# Весь код — в функции main: bash прочитает её целиком до запуска, поэтому новая
# версия этого же файла из архива не сломает выкатку на середине.
set -euo pipefail

main() {
  local project_dir log tmp site_host health_url
  local -a resolve
  project_dir="$(cd "$(dirname "$0")/.." && pwd)"
  log="${DEPLOY_LOG:-/var/log/builders-friend-deploy.log}"
  # Обрыв SSH не должен прерывать выкатку на полпути: HUP игнорируем, а tee -p
  # продолжает писать в журнал, даже если выход в SSH уже закрыт
  trap '' HUP
  exec > >(tee -p -a "$log") 2>&1

  exec 9>/var/lock/builders-friend-deploy.lock
  flock -n 9 || { echo "Выкатка уже идёт — эту пропускаем"; exit 1; }

  echo "=== $(date '+%F %T') выкатка: ${SSH_ORIGINAL_COMMAND:-без комментария}"

  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  tar -x -C "$tmp"   # архив приходит в stdin
  if [[ ! -f "$tmp/docker-compose.prod.yml" ]]; then
    echo "В архиве нет docker-compose.prod.yml — это не код сайта, выкатка отменена"
    exit 1
  fi

  cd "$project_dir"
  BACKUP_PREFIX=predeploy_ scripts/backup.sh

  tar -C "$tmp" -cf - . | tar -x -C "$project_dir"
  docker compose -f docker-compose.prod.yml --env-file .env.production --profile bot \
    up -d --build --remove-orphans
  docker image prune -f >/dev/null

  # Тот же адрес проверки, что и в scripts/healthcheck.sh: настоящий домен через сам сервер
  set -a; source .env.production; set +a
  site_host="${SITE_ADDRESS:-}"
  site_host="${site_host#*://}"
  site_host="${site_host%%[/ ,]*}"
  if [[ -n "$site_host" && "$site_host" != :* ]]; then
    health_url="https://$site_host/api/v1/health"
    resolve=(--resolve "$site_host:${HTTPS_PORT:-443}:127.0.0.1")
  else
    health_url="http://localhost:${HTTP_PORT:-80}/api/v1/health"
    resolve=()
  fi

  for _ in $(seq 1 30); do
    if curl -fsS -m 5 "${resolve[@]}" "$health_url" >/dev/null 2>&1; then
      echo "=== $(date '+%F %T') готово: сайт отвечает"
      exit 0
    fi
    sleep 5
  done
  echo "=== $(date '+%F %T') ОШИБКА: сайт не отвечает после выкатки ($health_url)"
  docker compose -f docker-compose.prod.yml --env-file .env.production ps
  exit 1
}

main "$@"
exit
