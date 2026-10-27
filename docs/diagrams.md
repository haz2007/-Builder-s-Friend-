# Диаграммы

Все диаграммы — в [Mermaid](https://mermaid.js.org): GitHub рисует их прямо на этой
странице, а исходник правится как обычный текст. Номера BR-xx ссылаются на
[бизнес-правила](business-rules.md).

## Содержание

1. [Архитектура](#1-архитектура)
2. [Модель данных](#2-модель-данных)
3. [Жизненный цикл заказа](#3-жизненный-цикл-заказа-br-16--br-19)
4. [Оформление заказа](#4-оформление-заказа-br-11--br-15-br-23)
5. [Смена статуса из Telegram](#5-смена-статуса-из-telegram-br-20--br-23-br-25)
6. [Сколько списать со склада](#6-сколько-списать-со-склада-br-03-br-05-br-14)
7. [Кто что может — варианты использования](#7-кто-что-может--варианты-использования)
8. [Контекст системы (C4, уровень 1)](#8-контекст-системы-c4-уровень-1)
9. [Защита от перегрузки и подбора пароля](#9-защита-от-перегрузки-и-подбора-пароля)
10. [Контейнеры (C4, уровень 2)](#10-контейнеры-c4-уровень-2)
11. [Компоненты backend (C4, уровень 3)](#11-компоненты-backend-c4-уровень-3)
12. [Развёртывание на сервере](#12-развёртывание-на-сервере)
13. [Бизнес-процесс: от заказа до выдачи](#13-бизнес-процесс-от-заказа-до-выдачи)
14. [Уведомления без потерь — transactional outbox](#14-уведомления-без-потерь--transactional-outbox-br-24-br-37)
15. [Заявка «Перезвоните мне»](#15-заявка-перезвоните-мне-br-42)
16. [Покупатель отменяет заказ](#16-покупатель-отменяет-заказ-br-18-br-19)

## 1. Архитектура

```mermaid
flowchart LR
    customer(["Покупатель"])
    admin(["Администратор"])

    subgraph server["Сервер — Docker Compose"]
        caddy["Caddy<br/>HTTPS, раздача сайта"]
        spa["Сайт и админка<br/>React + TypeScript"]
        api["Backend API<br/>FastAPI"]
        bot["Telegram-бот<br/>long polling"]
        db[("PostgreSQL")]
        uploads[("Фото товаров")]
    end

    relay["Посредник<br/>Cloudflare Worker"]
    telegram["Telegram Bot API"]
    maps["Яндекс Карты, 2ГИС,<br/>Google Карты"]

    customer -- "браузер" --> caddy
    admin -- "браузер (вход на сайте)" --> caddy
    caddy --> spa
    caddy -- "/api, /uploads" --> api
    api --> db
    api --> uploads
    api -- "уведомления (outbox)" --> relay
    bot <-- "команды и кнопки" --> relay
    relay <--> telegram
    bot --> db
    customer -. "чат с ботом" .-> telegram
    admin -. "чат с ботом" .-> telegram
    spa -. "карта и маршрут" .-> maps
```

<sub>Посредник нужен, потому что с российского сервера `api.telegram.org` закрыт: запросы бота идут через Cloudflare Worker, который пропускает только наш бот (`deploy/telegram-relay-worker.js`).</sub>

## 2. Модель данных

```mermaid
erDiagram
    USERS ||--o{ ORDERS : "оформляет"
    USERS ||--o| TELEGRAM_ACCOUNT_LINKS : "привязан к боту"
    USERS ||--o{ NOTIFICATIONS : "получает"
    CATEGORIES ||--o{ CATEGORIES : "подкатегории"
    CATEGORIES ||--o{ PRODUCTS : "основная категория"
    PRODUCTS }o--o{ CATEGORIES : "product_categories"
    PRODUCTS ||--|{ PRODUCT_VARIANTS : "варианты продажи"
    ORDERS ||--|{ ORDER_ITEMS : "позиции"
    PRODUCTS ||--o{ ORDER_ITEMS : ""
    PRODUCT_VARIANTS ||--o{ ORDER_ITEMS : ""
    ORDERS ||--o{ ORDER_STATUS_HISTORY : "история"
    ORDERS ||--o{ NOTIFICATIONS : ""
    USERS ||--o{ ORDER_STATUS_HISTORY : "сменил статус"
    USERS ||--o| PASSWORD_RESET_CODES : "код сброса"
    USERS ||--o{ AUDIT_LOG : "действия в админке"
    USERS ||--o{ CALLBACK_REQUESTS : "перезвонил"

    USERS {
        int id PK
        string phone UK "вход — только по номеру"
        string email "у старых аккаунтов"
        string role "CUSTOMER, ADMIN"
        int is_owner
    }
    CATEGORIES {
        int id PK
        string name UK
        int parent_id FK "null — раздел"
    }
    PRODUCTS {
        int id PK
        string name
        numeric stock_quantity "общий остаток"
        string unit "базовая единица"
        float thickness_mm
        float width_mm
        float length_mm
        int category_id FK
        int is_active
    }
    PRODUCT_VARIANTS {
        int id PK
        int product_id FK
        string name "Штука, Куб, Пачка"
        string unit
        numeric price
        numeric base_quantity "сколько базовых единиц"
        int is_active
    }
    ORDERS {
        int id PK
        int user_id FK
        string status
        numeric total_price
        datetime created_at
        string delivery_method "DELIVERY, PICKUP"
        string delivery_address
        string comment "распил, время доставки"
    }
    ORDER_ITEMS {
        int id PK
        int order_id FK
        int product_id FK
        int variant_id FK
        numeric quantity
        numeric price "снимок цены"
        string unit "снимок единицы"
        numeric base_quantity "снимок коэффициента"
    }
    ORDER_STATUS_HISTORY {
        int id PK
        int order_id FK
        string status
        datetime created_at
        int changed_by_id FK
    }
    NOTIFICATIONS {
        int id PK
        int user_id FK
        int order_id FK
        string message
        int is_read
    }
    TELEGRAM_ACCOUNT_LINKS {
        int id PK
        int user_id FK
        bigint telegram_user_id UK
        bigint telegram_chat_id
    }
    PASSWORD_RESET_CODES {
        int id PK
        int user_id FK, UK
        string code_hash "только хеш"
        datetime expires_at
        int attempts
    }
    AUDIT_LOG {
        int id PK
        int actor_id FK
        string action "product.updated, admin.added…"
        string summary "цена 600 → 650"
        json changes "было / стало"
        datetime created_at
    }
    CALLBACK_REQUESTS {
        int id PK
        string name
        string phone
        string comment
        text cart_summary "корзина по ценам из базы"
        numeric cart_total
        string status "NEW, DONE"
        int handled_by_id FK
    }
    TELEGRAM_OUTBOX {
        int id PK
        bigint chat_id
        text text
        string status "pending, sent, failed"
        int attempts
        datetime next_attempt_at
    }
```

## 3. Жизненный цикл заказа (BR-16 – BR-19)

```mermaid
stateDiagram-v2
    [*] --> NEW: покупатель оформил заказ
    NEW --> CONFIRMED: админ подтвердил
    CONFIRMED --> PREPARING: начали подготовку
    PREPARING --> READY_FOR_DELIVERY: заказ собран
    READY_FOR_DELIVERY --> ON_THE_WAY: доставка — машина выехала
    ON_THE_WAY --> DELIVERED: доставлен
    READY_FOR_DELIVERY --> DELIVERED: самовывоз — выдан на складе

    NEW --> CANCELLED: покупатель или админ
    CONFIRMED --> CANCELLED: админ
    PREPARING --> CANCELLED: админ
    READY_FOR_DELIVERY --> CANCELLED: админ

    DELIVERED --> [*]: просьба об отзыве (BR-25)
    CANCELLED --> [*]: товар вернулся на склад (BR-19)

    note right of ON_THE_WAY
        Из «В пути» отменить нельзя —
        только «Доставлен» (BR-17)
    end note
```

## 4. Оформление заказа (BR-11 – BR-15, BR-23)

```mermaid
sequenceDiagram
    autonumber
    actor C as Покупатель
    participant W as Сайт
    participant A as Backend API
    participant D as PostgreSQL
    participant T as Telegram

    C->>W: «Оформить заказ» (доставка или самовывоз)
    W->>A: POST /api/v1/orders (токен входа)
    A->>D: SELECT товары заказа FOR UPDATE (по возрастанию id)
    Note over A,D: блокировка в одном порядке —<br/>параллельные заказы не ловят deadlock
    A->>A: проверить варианты, целое количество,<br/>остаток по каждому товару (BR-13, BR-14)
    alt не хватает остатка
        A-->>W: 400 «Not enough stock»
    else всё в порядке
        A->>D: заказ, позиции со снимком цены,<br/>списание склада, история NEW
        A->>D: сообщения в telegram_outbox (та же транзакция)
        A->>D: COMMIT
        A-->>W: 200, заказ с allowed_statuses
        W-->>C: «Спасибо за заказ!»
        A--)T: после ответа отправляет очередь:<br/>покупателю и админам, вошедшим в бота (см. №14)
    end
```

## 5. Смена статуса из Telegram (BR-20 – BR-23, BR-25)

```mermaid
sequenceDiagram
    autonumber
    actor Ad as Администратор
    participant B as Telegram-бот
    participant D as PostgreSQL
    participant T as Telegram
    actor C as Покупатель

    T->>B: нажата кнопка «✅ Подтвердить заказ»
    B->>D: найти пользователя по Telegram (роль ADMIN?)
    B->>D: SELECT заказ FOR UPDATE
    alt переход недопустим (статус уже сменили)
        B-->>Ad: «Статус уже изменён — обнови карточку»
    else переход разрешён
        B->>D: новый статус, история, уведомление на сайте
        B->>D: COMMIT
        B-->>Ad: карточка заказа с новыми кнопками
        B->>T: другим админам — уведомление
        B->>T: покупателю — новый статус
        opt новый статус DELIVERED
            B->>T: покупателю — просьба об отзыве
        end
        T-->>C: сообщения в чате
    end
```

## 6. Сколько списать со склада (BR-03, BR-05, BR-14)

```mermaid
flowchart TD
    start["Позиция заказа:<br/>вариант + количество"] --> whole{"Нужно целое количество?<br/>(доска, куб, штука, упаковка)"}
    whole -- "да, а количество дробное" --> reject1["400: только целым количеством"]
    whole -- "нет или количество целое" --> factor["Коэффициент варианта:<br/>Штука = 1<br/>Куб = floor(1 / объём доски)<br/>Пачка 10 шт = 10"]
    factor --> need["Нужно базовых единиц =<br/>количество × коэффициент"]
    need --> sum["Сложить по всем вариантам<br/>одного товара"]
    sum --> check{"Хватает<br/>общего остатка?"}
    check -- "нет" --> reject2["400: не хватает на складе<br/>ничего не списано"]
    check -- "да" --> write["Списать со склада<br/>сохранить коэффициент в позиции"]
```

## 7. Кто что может — варианты использования

Связи «роль → действие». Владелец умеет всё, что администратор, плюс управляет
администраторами; администратор — всё, что покупатель (BR-29).

```mermaid
flowchart LR
    owner(["👑 Владелец"]) --> o
    admin(["🧰 Администратор"]) --> a
    customer(["🛒 Покупатель"]) --> c
    guest(["👤 Гость"]) --> g

    subgraph g["Каталог"]
        direction LR
        uc1(["Смотреть каталог,<br/>искать с опечатками"])
        uc2(["Собрать корзину:<br/>штуки, кубы, пачки"])
        uc12(["Посчитать материал<br/>по площади или длине"])
        uc13(["«Перезвоните мне»<br/>без регистрации"])
    end

    subgraph c["Свои заказы"]
        direction LR
        uc3(["Оформить заказ:<br/>доставка или самовывоз"])
        uc4(["Следить за статусом<br/>на сайте и в боте"])
        uc5(["Отменить<br/>новый заказ"])
        uc6(["Оставить отзыв<br/>на Яндекс Картах"])
        uc14(["Избранное, пароль,<br/>удаление аккаунта"])
    end

    subgraph a["Управление магазином"]
        direction LR
        uc7(["Вести заказы: следующий<br/>этап или отмена"])
        uc8(["Товары, варианты,<br/>размеры, фото"])
        uc9(["Категории<br/>и подкатегории"])
        uc10(["Аналитика,<br/>выгрузка в Excel"])
        uc15(["Перезвонить по заявке,<br/>напечатать бланк"])
        uc16(["Остатки, цены и новый<br/>товар с фото из бота"])
    end

    subgraph o["Команда"]
        direction LR
        uc11(["Назначать и снимать<br/>администраторов"])
    end

    uc3 -. "include" .-> chk(["Проверить остаток<br/>по всем позициям"])
```

## 8. Контекст системы (C4, уровень 1)

Система целиком и всё, с чем она общается снаружи.

```mermaid
flowchart TB
    customer["👤 <b>Покупатель</b><br/><small>заказывает доски, брус и крепёж<br/>с доставкой или самовывозом</small>"]
    staff["👤 <b>Владелец и администраторы</b><br/><small>ведут заказы, товары и склад,<br/>сами возят заказы</small>"]

    shop["<b>Друг Строителя</b><br/><small>сайт, админ-панель, API<br/>и Telegram-бот</small>"]

    telegram["<b>Telegram</b><br/><small>уведомления и кнопки<br/>смены статуса</small>"]
    maps["<b>Яндекс Карты · 2ГИС · Google Карты</b><br/><small>карта склада, маршрут, отзывы</small>"]
    le["<b>Let's Encrypt</b><br/><small>HTTPS-сертификат</small>"]
    cf["<b>Cloudflare Workers</b><br/><small>посредник до Telegram</small>"]

    customer -- "заказывает · HTTPS" --> shop
    staff -- "управляет · HTTPS" --> shop
    shop -- "уведомления, нажатия кнопок · Bot API" --> cf
    cf --> telegram
    shop -- "сертификат · ACME" --> le
    customer -. "статусы заказа" .-> telegram
    staff -. "новые заказы" .-> telegram
    customer -. "маршрут, отзыв" .-> maps

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef system fill:#1168bd,stroke:#0b4884,color:#fff
    classDef external fill:#8a8a8a,stroke:#6b6b6b,color:#fff
    class customer,staff person
    class shop system
    class telegram,maps,le,cf external
```

<sub>Синие — люди и наша система, серые — внешние сервисы. Устройство системы внутри — на [схеме архитектуры](#1-архитектура).</sub>

## 9. Защита от перегрузки и подбора пароля

```mermaid
flowchart TD
    req["Запрос: вход, регистрация, заказ<br/>или пароль в Telegram-боте"] --> key["Ключ: IP покупателя<br/>(в боте — Telegram ID)"]
    key --> win{"Попыток за окно<br/>меньше лимита?"}
    win -- "да" --> ok["Обрабатываем запрос"]
    win -- "нет" --> stop["429 «Слишком много попыток»<br/>+ Retry-After"]
    ok --> db[("PostgreSQL")]
    db --> chk{"CHECK в базе:<br/>остаток ≥ 0, статус и роль<br/>из списка, цена ≥ 0"}
    chk -- "нарушено" --> rollback["Транзакция откатывается —<br/>неверные данные не записываются"]
    chk -- "в порядке" --> saved["Сохранено"]
```

| Действие | Лимит | Ключ |
|---|---|---|
| Вход на сайте | 10 попыток за 5 минут | IP |
| Регистрация | 5 за час | IP |
| Оформление заказа | 30 за час | IP |
| Вход в Telegram-боте | 5 попыток за 10 минут | Telegram ID |
| Код сброса пароля: запросить / ввести | 3 / 10 за 15 минут | IP |
| Заявка «Перезвоните мне» | 5 за час | IP |
| Вход на сервер по SSH | 5 ошибок — бан на час (fail2ban), вход только по ключу | IP |

## 10. Контейнеры (C4, уровень 2)

Из чего состоит система «Друг Строителя» и чем контейнеры обмениваются.

```mermaid
flowchart TB
    customer["👤 <b>Покупатель</b>"]
    staff["👤 <b>Администратор</b>"]

    subgraph shop["Друг Строителя — один VPS, Docker Compose"]
        web["<b>web</b> · Caddy<br/><small>HTTPS, статика React,<br/>SEO-теги в head</small>"]
        spa["<b>Сайт и панель</b> · React 19, TypeScript<br/><small>каталог, корзина, кабинет,<br/>админка — в браузере</small>"]
        api["<b>backend</b> · FastAPI<br/><small>REST API, бизнес-правила,<br/>отправка outbox</small>"]
        bot["<b>bot</b> · Python<br/><small>long polling, кнопки,<br/>outbox каждые 3 с</small>"]
        db[("<b>db</b> · PostgreSQL 15<br/><small>заказы, склад, журнал,<br/>pg_trgm</small>")]
        files[("Фото<br/><small>WebP в томе uploads</small>")]
    end

    cf["<b>Cloudflare Worker</b><br/><small>посредник</small>"]
    tg["<b>Telegram</b>"]

    customer -- "HTTPS" --> web
    staff -- "HTTPS" --> web
    web -- "отдаёт" --> spa
    spa -- "JSON /api · JWT" --> web
    web -- "reverse_proxy" --> api
    api -- "SQL" --> db
    api -- "сохраняет" --> files
    bot -- "SQL" --> db
    api -- "sendMessage" --> cf
    bot -- "getUpdates, sendMessage" --> cf
    cf --> tg

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef container fill:#438dd5,stroke:#2e6295,color:#fff
    classDef external fill:#8a8a8a,stroke:#6b6b6b,color:#fff
    class customer,staff person
    class web,spa,api,bot,db,files container
    class cf,tg external
```

<sub>Отдельной формы входа у админки нет: администратор входит на сайте, токен тот же, а кнопка «Панель» ведёт в `/admin`.</sub>

## 11. Компоненты backend (C4, уровень 3)

Слои внутри FastAPI: роутеры принимают запрос и проверяют права, сервисы держат
бизнес-правила, модели — схему базы.

```mermaid
flowchart LR
    spa["Сайт и панель"]
    botc["Telegram-бот"]

    subgraph backend["backend · FastAPI"]
        direction TB
        subgraph routers["routers/ — HTTP"]
            r_auth["auth<br/><small>вход по телефону, регистрация,<br/>сброс и смена пароля, удаление</small>"]
            r_shop["products · categories<br/><small>каталог, поиск, подсказки,<br/>варианты, фото</small>"]
            r_orders["orders · notifications<br/><small>оформление, отмена, статусы</small>"]
            r_admin["admin · admins · users<br/><small>аналитика, журнал, Excel,<br/>роли, временный пароль</small>"]
            r_calls["callbacks<br/><small>«Перезвоните мне»</small>"]
            r_seo["seo<br/><small>head и sitemap</small>"]
        end
        subgraph services["services/ — бизнес-правила"]
            s_order["order_service<br/><small>переходы статусов, остатки</small>"]
            s_variant["variant_service<br/><small>штуки ↔ кубы</small>"]
            s_notify["order_notifications<br/><small>outbox, повторы</small>"]
            s_reports["reports · export<br/><small>SQL-отчёты, xlsx</small>"]
            s_misc["audit · images · search<br/>account · password_reset · callbacks"]
        end
        models["models.py · SQLAlchemy 2<br/><small>типизированные модели, CHECK</small>"]
    end
    db[("PostgreSQL")]

    spa --> routers
    routers --> services
    botc --> services
    services --> models
    models --> db
```

<sub>Бот не ходит в API по HTTP — он вызывает те же сервисы напрямую, поэтому правила для сайта и бота одни.</sub>

## 12. Развёртывание на сервере

```mermaid
flowchart TB
    subgraph vps["VPS · Ubuntu 24.04 · 1 vCPU, 1 ГБ RAM + swap 2 ГБ"]
        direction TB
        ufw["ufw: открыты 22, 80, 443<br/>fail2ban, SSH только по ключу"]
        subgraph compose["Docker Compose · docker-compose.prod.yml"]
            web["web · Caddy<br/>лимит 100 МБ"]
            api["backend · uvicorn<br/>лимит 300 МБ"]
            bot["bot<br/>лимит 160 МБ"]
            db[("db · PostgreSQL<br/>лимит 320 МБ")]
        end
        vol_db[("том db_data")]
        vol_up[("том uploads")]
        vol_caddy[("том caddy_data<br/>сертификаты")]
        cron["cron<br/>03:30 — scripts/backup.sh<br/>каждые 5 мин — healthcheck.sh"]
    end

    le["Let's Encrypt"]
    cf["Cloudflare Worker"]
    dns["DNS reg.ru: builders-friend.ru<br/>(www и старый duckdns — редирект)"]

    db --- vol_db
    api --- vol_up
    web --- vol_caddy
    cron -. "pg_dump + фото" .-> vol_db
    cron -. "при поломке — сообщение" .-> cf
    web -- "ACME, продление" --> le
    api --> cf
    bot --> cf
    dns -. "A-запись на IP" .-> vps
```

<sub>Обновление — `docker compose … up -d --build`: миграции базы применяются сами при старте backend.</sub>

## 13. Бизнес-процесс: от заказа до выдачи

Дорожки — кто выполняет шаг. Упрощённая блок-схема; тот же процесс в настоящей нотации BPMN 2.0 — [docs/bpmn/order-process.bpmn](bpmn/order-process.bpmn) (картинка — [order-process.svg](bpmn/order-process.svg)).

```mermaid
flowchart LR
    subgraph lane_c["Покупатель"]
        c1(["Нужен материал"]) --> c2["Найти товар,<br/>посчитать количество"]
        c2 --> c3{"Есть аккаунт<br/>или готов завести?"}
        c3 -- "да" --> c4["Оформить заказ:<br/>доставка / самовывоз,<br/>комментарий"]
        c3 -- "нет" --> c5["«Перезвоните мне»:<br/>имя и телефон"]
        c9["Получить заказ"] --> c10(["Отзыв на Картах"])
    end

    subgraph lane_s["Сайт и бот"]
        s1{"Хватает<br/>на складе?"}
        s1 -- "нет" --> s2["Ошибка,<br/>ничего не списано"]
        s1 -- "да" --> s3["Списать склад,<br/>заказ NEW,<br/>уведомить админов"]
        s4["Сообщить покупателю<br/>о каждом статусе"]
    end

    subgraph lane_a["Администратор"]
        a1["Позвонить, подтвердить<br/>доставку и оплату"] --> a2["Собрать заказ"]
        a2 --> a3{"Доставка?"}
        a3 -- "да" --> a4["Отвезти: «В пути»<br/>→ «Доставлен»"]
        a3 -- "нет" --> a5["«Готов к выдаче»<br/>→ «Выдан»"]
        a6["Перезвонить по заявке,<br/>оформить заказ"]
    end

    c4 --> s1
    s2 --> c2
    s3 --> a1
    c5 --> a6
    a6 --> a1
    a1 --> s4
    a4 --> c9
    a5 --> c9
```

## 14. Уведомления без потерь — transactional outbox (BR-24, BR-37)

```mermaid
sequenceDiagram
    autonumber
    participant A as Backend / бот
    participant D as PostgreSQL
    participant S as Отправитель (API и бот)
    participant R as Cloudflare Worker
    participant T as Telegram

    A->>D: BEGIN — изменение заказа
    A->>D: INSERT telegram_outbox (pending)
    A->>D: COMMIT — заказ и сообщения вместе
    Note over A,D: упадёт процесс после COMMIT —<br/>сообщения уже в базе
    loop API после ответа, бот каждые 3 с
        S->>D: SELECT … FOR UPDATE SKIP LOCKED<br/>pending, у которых подошло время
        Note over S,D: два отправителя не возьмут<br/>одно сообщение
        S->>R: sendMessage
        R->>T: sendMessage
        alt доставлено
            S->>D: status = sent
        else ошибка сети или Telegram
            S->>D: attempts + 1, следующая попытка<br/>через 10 с, 20 с, 40 с…
            opt 8 попыток не удалось
                S->>D: status = failed — видно в /api/v1/health
            end
        end
    end
```

## 15. Заявка «Перезвоните мне» (BR-42)

```mermaid
sequenceDiagram
    autonumber
    actor G as Гость
    participant W as Сайт
    participant A as Backend API
    participant D as PostgreSQL
    participant B as Бот
    actor Ad as Администратор

    G->>W: имя, телефон, согласие,<br/>корзина (id вариантов и количество)
    W->>A: POST /api/v1/callback-requests
    A->>A: лимит 5 в час с IP,<br/>номер → +7XXXXXXXXXX
    A->>D: цены вариантов из базы —<br/>цены из браузера не принимаются
    A->>D: заявка NEW + сообщения админам в outbox
    A-->>W: «Перезвоним!»
    A--)Ad: Telegram: телефон, корзина, кнопка «✅ Перезвонили»
    Ad->>B: «✅ Перезвонили»
    B->>D: SELECT заявка FOR UPDATE → DONE,<br/>кто и когда, запись в журнал
    B-->>Ad: сообщение без кнопки, «Перезвонили · имя админа»
```

## 16. Покупатель отменяет заказ (BR-18, BR-19)

```mermaid
sequenceDiagram
    autonumber
    actor C as Покупатель
    participant W as Сайт или бот
    participant A as Backend
    participant D as PostgreSQL
    actor Ad as Администраторы

    C->>W: «Отменить заказ»
    W->>A: POST /api/v1/orders/{id}/cancel
    A->>D: SELECT заказ FOR UPDATE
    alt статус не NEW (уже подтверждён)
        A-->>W: 400 — отменить можно только новый,<br/>дальше — по телефону
    else NEW
        A->>D: товары заказа FOR UPDATE (по id)
        A->>D: вернуть на склад базовые единицы<br/>(для кубов — штуки по коэффициенту)
        A->>D: статус CANCELLED, история, outbox
        A->>D: COMMIT
        A-->>W: заказ отменён
        A--)Ad: «Покупатель отменил заказ №…»
    end
```
