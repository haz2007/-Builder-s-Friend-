# Деплой на сервер

Весь проект запускается одной командой через Docker Compose на одном VPS:

```
Интернет ─► Caddy (80/443, HTTPS) ─┬─► сайт (статические файлы React)
                                  ├─► /api, /uploads ─► backend (FastAPI)
                                  │                       │
              Telegram ◄── bot ───┴───────────────────────┴─► PostgreSQL
```

| Сервис | Что делает |
|---|---|
| `web` | Caddy: раздаёт сайт, проксирует API и фото, сам выпускает и продлевает HTTPS-сертификат |
| `backend` | FastAPI; при старте сам приводит базу в актуальное состояние (`manage.py migrate`) |
| `bot` | Telegram-бот (тот же образ, другая команда) |
| `db` | PostgreSQL 15, наружу не открыт |

## 1. Сервер

Подойдёт любой VPS с Ubuntu 22.04/24.04: **1 vCPU, 2 ГБ RAM, 20 ГБ диска** — этого хватит
магазину с запасом. Подходящие варианты:

- **Timeweb Cloud / Selectel / REG.RU** — серверы в России, оплата картой РФ, быстрый сайт
  для покупателей. Если `api.telegram.org` с сервера недоступен — задайте `TELEGRAM_PROXY`.
- Сервер за границей — Telegram работает без прокси, но сложнее с оплатой.

Домен (`.ru`) — у любого регистратора, например REG.RU или Timeweb. В DNS добавьте
A-запись `@` (и при желании `www`) на IP сервера.

## 2. Установка Docker на сервер

```bash
curl -fsSL https://get.docker.com | sh
```

## 3. Запуск

```bash
git clone https://github.com/haz2007/wood-commerce.git
cd wood-commerce
cp .env.production.example .env.production
nano .env.production        # домен, пароль базы, SECRET_KEY, токен бота
```

Сгенерировать секреты:
```bash
openssl rand -base64 24    # POSTGRES_PASSWORD
openssl rand -hex 32       # SECRET_KEY
```

Запуск сайта и бота:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production --profile bot up -d --build
```

Без Telegram-бота — то же самое без `--profile bot`.

Первичная настройка:
```bash
# пробные товары (по желанию)
docker compose -f docker-compose.prod.yml --env-file .env.production exec backend python seed_demo.py
# зарегистрируйтесь на сайте по телефону, затем назначьте себя владельцем
docker compose -f docker-compose.prod.yml --env-file .env.production exec backend python manage.py set-owner +79991234567
```

Сайт откроется на `https://ваш-домен`, админка — `/admin`.

## 4. Обновление после изменений в коде

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production --profile bot up -d --build
```

Миграции базы применяются автоматически при старте backend.

## 5. Бэкапы

Ежедневный дамп базы (cron, `crontab -e`):
```bash
0 3 * * * cd ~/wood-commerce && docker compose -f docker-compose.prod.yml --env-file .env.production exec -T db pg_dump -U wood -Fc wood_commerce > ~/backups/wood_$(date +\%F).dump
```

Фото товаров лежат в томе `uploads`, база — в томе `db_data`.

## Полезное

```bash
# логи
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend bot
# состояние сервисов
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```
