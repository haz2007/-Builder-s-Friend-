# Диаграммы

Все диаграммы — в [Mermaid](https://mermaid.js.org): GitHub рисует их прямо на этой
странице, а исходник правится как обычный текст. Номера BR-xx ссылаются на
[бизнес-правила](business-rules.md).

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

    telegram["Telegram Bot API"]
    maps["Яндекс Карты, 2ГИС,<br/>Google Maps"]

    customer -- "браузер" --> caddy
    admin -- "браузер" --> caddy
    caddy --> spa
    caddy -- "/api, /uploads" --> api
    api --> db
    api --> uploads
    api -- "уведомления о заказах" --> telegram
    bot <-- "команды и кнопки" --> telegram
    bot --> db
    customer -. "чат с ботом" .-> telegram
    admin -. "чат с ботом" .-> telegram
    spa -. "карта и маршрут" .-> maps
```

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

    USERS {
        int id PK
        string phone UK
        string email UK
        string role "CUSTOMER, ADMIN, DRIVER"
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
        float stock_quantity "общий остаток"
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
        float price
        float base_quantity "сколько базовых единиц"
        int is_active
    }
    ORDERS {
        int id PK
        int user_id FK
        string status
        float total_price
        string delivery_method "DELIVERY, PICKUP"
        string delivery_address
    }
    ORDER_ITEMS {
        int id PK
        int order_id FK
        int product_id FK
        int variant_id FK
        float quantity
        float price "снимок цены"
        string unit "снимок единицы"
        float base_quantity "снимок коэффициента"
    }
    ORDER_STATUS_HISTORY {
        int id PK
        int order_id FK
        string status
        datetime created_at
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
```

## 3. Жизненный цикл заказа (BR-16 – BR-19)

```mermaid
stateDiagram-v2
    [*] --> NEW: покупатель оформил заказ
    NEW --> CONFIRMED: админ подтвердил
    CONFIRMED --> PREPARING: начали подготовку
    PREPARING --> READY_FOR_DELIVERY: заказ собран
    READY_FOR_DELIVERY --> ASSIGNED_TO_DRIVER: назначен водитель
    ASSIGNED_TO_DRIVER --> ON_THE_WAY: машина выехала
    ON_THE_WAY --> DELIVERED: доставлен или выдан

    NEW --> CANCELLED: покупатель или админ
    CONFIRMED --> CANCELLED: админ
    PREPARING --> CANCELLED: админ
    READY_FOR_DELIVERY --> CANCELLED: админ
    ASSIGNED_TO_DRIVER --> CANCELLED: админ

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
        A->>D: COMMIT
        A-->>W: 200, заказ с allowed_statuses
        W-->>C: «Спасибо за заказ!»
        A--)T: после ответа (фоновая задача):<br/>покупателю и админам, вошедшим в бота
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
