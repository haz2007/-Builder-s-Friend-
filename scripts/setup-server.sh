#!/usr/bin/env bash
# Первичная настройка чистого сервера Ubuntu 22.04/24.04 (запускать от root один раз):
#   sudo bash scripts/setup-server.sh
#
# Что делает:
#   1. swap 2 ГБ — чтобы сборка сайта и база не упирались в 1 ГБ памяти;
#   2. Docker и Docker Compose;
#   3. файрвол: открыты только SSH, 80 и 443; fail2ban от подбора пароля SSH;
#   4. ежедневный бэкап базы и фото в 03:30 (scripts/backup.sh);
#   5. проверка каждые 5 минут (scripts/healthcheck.sh) — при поломке пишет в Telegram.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Запусти от root: sudo bash scripts/setup-server.sh" >&2
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SWAP_SIZE="${SWAP_SIZE:-2G}"

echo "==> Swap ${SWAP_SIZE}"
if swapon --show | grep -q .; then
  echo "    swap уже есть — пропускаю"
else
  fallocate -l "$SWAP_SIZE" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
# Пользоваться swap только когда память действительно кончилась
sysctl -q vm.swappiness=10
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf

echo "==> Docker"
if command -v docker >/dev/null; then
  echo "    Docker уже установлен: $(docker --version)"
else
  curl -fsSL https://get.docker.com | sh
fi
# Docker из пакетов Ubuntu ставится без «docker compose» — доставляем плагин
if ! docker compose version >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq docker-compose-v2 >/dev/null
fi
systemctl enable --now docker >/dev/null

echo "==> Файрвол и защита SSH"
apt-get install -y -qq ufw fail2ban cron >/dev/null
# Боты постоянно подбирают пароли к SSH: 5 ошибок — бан на час
printf '[sshd]\nenabled = true\nmaxretry = 5\nbantime = 1h\n' > /etc/fail2ban/jail.d/sshd.local
systemctl enable --now fail2ban cron >/dev/null
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
ufw status | sed 's/^/    /'

echo "==> Ежедневный бэкап"
chmod +x "$PROJECT_DIR/scripts/backup.sh" "$PROJECT_DIR/scripts/restore.sh" "$PROJECT_DIR/scripts/healthcheck.sh" \
  "$PROJECT_DIR/scripts/purge-expired.sh"
CRON_LINE="30 3 * * * $PROJECT_DIR/scripts/backup.sh >> /var/log/wood-backup.log 2>&1"
HEALTH_LINE="*/5 * * * * $PROJECT_DIR/scripts/healthcheck.sh >> /var/log/wood-health.log 2>&1"
# Сроки хранения персональных данных (152-ФЗ): после ночного бэкапа
PURGE_LINE="45 3 * * * $PROJECT_DIR/scripts/purge-expired.sh >> /var/log/wood-purge.log 2>&1"
# На новом сервере crontab пуст: «crontab -l» и grep без совпадений не должны
# останавливать скрипт (set -o pipefail)
EXISTING_CRON="$(crontab -l 2>/dev/null | grep -v 'scripts/backup.sh' | grep -v 'scripts/healthcheck.sh' \
  | grep -v 'scripts/purge-expired.sh' || true)"
printf '%s\n%s\n%s\n%s\n' "$EXISTING_CRON" "$CRON_LINE" "$HEALTH_LINE" "$PURGE_LINE" | sed '/^$/d' | crontab -
echo "    $CRON_LINE"
echo "    $HEALTH_LINE"
echo "    $PURGE_LINE"

echo
echo "Готово. Дальше: заполни .env.production и запусти проект (см. DEPLOY.md)."
