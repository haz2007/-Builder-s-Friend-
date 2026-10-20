#!/usr/bin/env bash
# Первичная настройка чистого сервера Ubuntu 22.04/24.04 (запускать от root один раз):
#   sudo bash scripts/setup-server.sh
#
# Что делает:
#   1. swap 2 ГБ — чтобы сборка сайта и база не упирались в 1 ГБ памяти;
#   2. Docker и Docker Compose;
#   3. файрвол: открыты только SSH, 80 и 443;
#   4. ежедневный бэкап базы и фото в 03:30 (scripts/backup.sh).
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
systemctl enable --now docker >/dev/null

echo "==> Файрвол"
apt-get install -y -qq ufw >/dev/null
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
ufw status | sed 's/^/    /'

echo "==> Ежедневный бэкап"
chmod +x "$PROJECT_DIR/scripts/backup.sh" "$PROJECT_DIR/scripts/restore.sh"
CRON_LINE="30 3 * * * $PROJECT_DIR/scripts/backup.sh >> /var/log/wood-backup.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'scripts/backup.sh' ; echo "$CRON_LINE" ) | crontab -
echo "    $CRON_LINE"

echo
echo "Готово. Дальше: заполни .env.production и запусти проект (см. DEPLOY.md)."
