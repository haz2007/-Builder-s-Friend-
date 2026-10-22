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

Подойдёт любой VPS на **KVM** с Ubuntu 22.04/24.04: **1 vCPU, 1 ГБ RAM, 10–15 ГБ диска**.
В работе проект занимает около 150–250 МБ памяти; лимиты контейнеров в
`docker-compose.prod.yml` рассчитаны на 1 ГБ, а сборке сайта помогает swap.

| Сервис | Лимит памяти |
|---|---|
| `db` (PostgreSQL, настроен под маленький сервер) | 320 МБ |
| `backend` (1 процесс API, `WEB_CONCURRENCY=1`) | 300 МБ |
| `bot` | 160 МБ |
| `web` (Caddy) | 100 МБ |

- Серверы в России (Beget, VDSina, FirstVDS, Timeweb Cloud) — оплата картой РФ. Если
  `api.telegram.org` с сервера недоступен — задайте `TELEGRAM_PROXY`.
- OpenVZ-тарифы не подходят: на них не работает Docker. Обычный хостинг для сайтов
  («сайты, FTP, CP») — тоже: нужен VPS с root-доступом.
- На 2 ГБ и больше можно поставить `WEB_CONCURRENCY=2`.

Домен (`.ru`) — у любого регистратора, например REG.RU. В DNS добавьте
A-запись `@` (и при желании `www`) на IP сервера.

## 2. Подготовка сервера

```bash
git clone https://github.com/haz2007/-Builder-s-Friend-.git builders-friend
cd builders-friend
sudo bash scripts/setup-server.sh
```

Скрипт один раз настраивает чистый сервер:
- swap 2 ГБ (`SWAP_SIZE=4G` — чтобы изменить);
- Docker и Docker Compose;
- файрвол: открыты только SSH, 80 и 443;
- ежедневный бэкап в 03:30 (`scripts/backup.sh`, лог — `/var/log/wood-backup.log`);
- в 03:45 — удаление данных с истёкшим сроком хранения (`scripts/purge-expired.sh`, лог —
  `/var/log/wood-purge.log`): копии сообщений Telegram старше 7 дней, заявки на звонок через
  30 дней после звонка, контакты в завершённых заказах удалённых аккаунтов (BR-46).

## 3. Запуск

```bash
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

Перед запуском для покупателей (152-ФЗ):
- реквизиты продавца — в `SELLER` в `frontend/src/shop/contacts.ts`; они показываются
  в подвале, в согласии (`/consent`) и в политике (`/privacy`);
- владелец ИП подаёт **уведомление об обработке персональных данных** в Роскомнадзор
  (портал pd.rkn.gov.ru, вход через Госуслуги) — до того, как сайт начнёт принимать заказы;
- там же — **уведомление о трансграничной передаче** (ст. 12 152-ФЗ): заказы с именем,
  телефоном и адресом уходят админам в Telegram через Cloudflare Worker, а это серверы
  за пределами России. Получатели: Telegram и Cloudflare, Inc. (США);
- данные покупателей из России хранятся на сервере в России — для настоящего запуска
  нужен российский VPS.

## 4. Обновление после изменений в коде

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production --profile bot up -d --build
```

Миграции базы применяются автоматически при старте backend.

## 5. Бэкапы и восстановление

```bash
scripts/backup.sh                     # вручную; по расписанию — каждую ночь
ls backups/                           # db_<дата>.dump и uploads_<дата>.tar.gz
```

Хранятся последние 14 дней (`BACKUP_KEEP_DAYS`).

### Копия бэкапов на Яндекс Диске

Сервер может пропасть вместе с бэкапами, поэтому после каждого ночного бэкапа
`scripts/offsite-backup.sh` кладёт копию на Яндекс Диск — в папку
`builders-friend-backups/`, 7 файлов по дням недели (`db_1.dump` … `db_7.dump` и
архивы фото): место на Диске не растёт. Если копия не ушла за сутки, мониторинг
напишет в Telegram.

Бесплатный Диск не пускает по WebDAV («not available for the free tariff»), поэтому
используется REST API с OAuth-токеном. Настройка — один раз:

1. [oauth.yandex.ru/client/new](https://oauth.yandex.ru/client/new) — приложение
   «Веб-сервисы», Redirect URI `https://oauth.yandex.ru/verification_code`. Личные
   данные (почта, телефон, имя) не нужны; в «Дополнительных» — два доступа:
   «Запись в любом месте на Диске» (`cloud_api:disk.write`) и «Чтение всего Диска»
   (`cloud_api:disk.read`). Сохранить ClientID.
2. Открыть `https://oauth.yandex.ru/authorize?response_type=token&client_id=<ClientID>`,
   «Разрешить», скопировать токен.
3. На сервере: `sudo bash scripts/set-offsite-credentials.sh` — вставить токен (не
   отображается). Скрипт проверит его на Диске и сохранит в
   `/root/.config/builders-friend/yandex-disk.token` (права 600, не в проекте).

Токен живёт около года: когда истечёт, мониторинг сообщит — повторить шаги 2–3.

Восстановиться можно и с Диска: скачать нужный `db_N.dump` (и `uploads_N.tar.gz`)
в `backups/` и запустить `scripts/restore.sh`, как ниже.

Восстановление (перед заменой скрипт сам сделает свежий бэкап текущей базы):
```bash
scripts/restore.sh backups/db_2026-10-20_033000.dump backups/uploads_2026-10-20_033000.tar.gz
```

## Мониторинг

`scripts/healthcheck.sh` (cron каждые 5 минут, ставит `setup-server.sh`) проверяет:
API и базу (`/api/v1/health`), контейнеры, место на диске, свежесть бэкапа и застрявшие
сообщения в Telegram. При поломке пишет **владельцу в Telegram** один раз, когда всё
восстановилось — ещё раз. Проверить вручную, ничего не отправляя:
```bash
HEALTHCHECK_DRY_RUN=1 scripts/healthcheck.sh
```

Если упадёт **весь сервер**, этот скрипт уже ничего не пошлёт. На этот случай — бесплатный
внешний монитор: [UptimeRobot](https://uptimerobot.com) → *New monitor* → HTTP(s) →
`https://ваш-домен/api/v1/health`, интервал 5 минут, уведомления на почту или в Telegram.

## 6. Если Telegram недоступен с сервера

С российского сервера `api.telegram.org` может быть закрыт — тогда сайт работает,
а бот не получает сообщений. Проверка (на сервере):
```bash
curl -s -m 10 -o /dev/null -w "%{http_code}\n" https://api.telegram.org   # 302 — доступен
```

Бесплатный обход — посредник на Cloudflare Workers (100 000 запросов в сутки бесплатно):
1. [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers & Pages** → **Create** → **Worker**,
   имя `telegram-relay` → **Deploy** → **Edit code**.
2. Вставить код из `deploy/telegram-relay-worker.js` → **Deploy**.
3. **Settings → Variables**: `BOT_ID` = число до двоеточия в токене бота
   (Worker пропускает только этого бота).
4. В `.env.production`:
   ```
   TELEGRAM_API_URL=https://telegram-relay.<ваше-имя>.workers.dev
   ```
5. Перезапустить: `docker compose -f docker-compose.prod.yml --env-file .env.production --profile bot up -d`

Второй вариант — свой прокси: `TELEGRAM_PROXY=socks5://user:pass@host:port`.

## 7. Если данные покупателей утекли

Утечка — это когда данные покупателей увидел или забрал кто-то посторонний: взлом
сервера или админки, украденный пароль администратора, бэкап или выгрузка Excel,
попавшие не туда. По ст. 21 152-ФЗ сроки жёсткие, за молчание — штраф 1–3 млн ₽.

1. **Сразу:** закрыть дыру — сменить пароли и `SECRET_KEY` в `.env.production`
   (после смены все выйдут из аккаунтов), снять права у подозрительных админов,
   при взломе сервера — выключить его (`docker compose ... down`).
2. **В течение 24 часов** — уведомить Роскомнадзор (pd.rkn.gov.ru → «Уведомление об
   инциденте»): что случилось, чьи данные и сколько, что уже сделано, кто контактное лицо.
3. **В течение 72 часов** — второе уведомление: итоги разбора (причина и кто виноват,
   если известно).
4. Записать, что произошло и что сделано: журнал действий в админке (раздел «Журнал»)
   и логи (`docker compose ... logs backend`) помогут понять, кто и что видел.

## Полезное

```bash
# логи
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend bot
# состояние сервисов
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```
