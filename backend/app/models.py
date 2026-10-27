import math
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    event,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .database import Base

# Допустимые значения — их же проверяет база (CHECK), чтобы ошибка в коде
# не записала неизвестный статус или роль
USER_ROLES = ("CUSTOMER", "ADMIN")
ORDER_STATUSES = (
    "NEW",
    "CONFIRMED",
    "PREPARING",
    "READY_FOR_DELIVERY",
    "ON_THE_WAY",
    "DELIVERED",
    "CANCELLED",
)
DELIVERY_METHODS = ("DELIVERY", "PICKUP")


# Деньги — NUMERIC(12, 2), количества — NUMERIC(12, 3): база хранит их точно,
# без копеечных погрешностей float. В Python они читаются как float
# (asdecimal=False): расчёты в коде остаются простыми, а округление до копеек
# и тысячных делает PostgreSQL.
Money = Numeric(12, 2, asdecimal=False)
Quantity = Numeric(12, 3, asdecimal=False)


def one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


# Единицы, для которых количество в варианте считается по объёму доски
CUBIC_UNITS = {"м3", "м³", "куб", "куб.м", "м.куб"}


def normalize_unit(unit: str | None) -> str:
    """«Шт.» и «шт» — одна и та же единица."""
    return (unit or "").strip().lower().rstrip(".")


def is_cubic_unit(unit: str | None) -> bool:
    return normalize_unit(unit) in CUBIC_UNITS


def is_piece_unit(unit: str | None) -> bool:
    return normalize_unit(unit) == "шт"


def pieces_in_cubic_meter(
    thickness_mm: float | None,
    width_mm: float | None,
    length_mm: float | None,
) -> int | None:
    """Сколько целых досок входит в 1 м³: 27,333 → 27."""
    if not thickness_mm or not width_mm or not length_mm:
        return None

    board_volume_m3 = thickness_mm * width_mm * length_mm / 1_000_000_000
    # Небольшой допуск, чтобы 1 / 0.05 не превратилось в 19.999…
    return math.floor(1 / board_volume_m3 + 1e-9)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(one_of("role", USER_ROLES), name="ck_users_role"),
        # Один телефон — один аккаунт (вход и регистрация по телефону)
        Index("ix_users_phone_unique", "phone", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="CUSTOMER")
    # Владелец магазина: администратор, который управляет другими админами
    is_owner: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Когда покупатель согласился с политикой конфиденциальности (152-ФЗ).
    # Пусто — у аккаунтов, созданных до появления согласия, и у админов
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(DateTime)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# Дополнительные категории товара (основная хранится в products.category_id)
product_categories = Table(
    "product_categories",
    Base.metadata,
    Column(
        "product_id",
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # Первичный ключ (product_id, category_id) не помогает искать товары категории
    Index("ix_product_categories_category_id", "category_id"),
)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    # Подкатегория указывает на родителя: «Доска» → «Пиломатериалы»
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "categories.id",
            ondelete="SET NULL",
            name="fk_categories_parent_id_categories",
        ),
        index=True,
    )

    # Порядок в магазине: меньше — выше (пиломатериалы первыми), при равенстве — по алфавиту
    position: Mapped[int] = mapped_column(Integer, default=100, server_default="100")

    products: Mapped[list["Product"]] = relationship(back_populates="category")
    parent: Mapped["Category | None"] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list["Category"]] = relationship(back_populates="parent", order_by="Category.name")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_not_negative"),
        CheckConstraint("price >= 0", name="ck_products_price_not_negative"),
        # Поиск с опечатками: триграммы названия (pg_trgm), см. services/search.py
        Index(
            "ix_products_name_trgm",
            text("lower(name) gin_trgm_ops"),
            postgresql_using="gin",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(1000))
    price: Mapped[float] = mapped_column(Money)
    # Общий остаток товара в базовой единице unit (для досок — в штуках)
    stock_quantity: Mapped[float] = mapped_column(Quantity, default=0)
    unit: Mapped[str] = mapped_column(String(20))

    # Размеры доски в мм; если заданы, остаток ведётся в штуках
    thickness_mm: Mapped[float | None] = mapped_column(Float)
    width_mm: Mapped[float | None] = mapped_column(Float)
    length_mm: Mapped[float | None] = mapped_column(Float)

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)

    is_active: Mapped[int] = mapped_column(Integer, default=1)
    image_url: Mapped[str | None] = mapped_column(String(500))

    category: Mapped["Category"] = relationship(back_populates="products")
    categories: Mapped[list["Category"]] = relationship(secondary=product_categories)
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductVariant.id",
    )

    @property
    def category_ids(self) -> list[int]:
        # Основная категория входит всегда, даже если связь не записана
        ids = {category.id for category in self.categories}
        if self.category_id:
            ids.add(self.category_id)
        return sorted(ids)

    @property
    def pieces_per_cubic_meter(self) -> int | None:
        return pieces_in_cubic_meter(
            self.thickness_mm,
            self.width_mm,
            self.length_mm,
        )


class ProductVariant(Base):
    """Вариант продажи товара: например, доска за штуку или за м³.

    Цена у каждого варианта своя, а склад общий — в товаре.
    Одна единица варианта списывает со склада base_quantity базовых
    единиц: «Штука» = 1, «м³» = сколько досок в кубе (например, 27).
    """

    __tablename__ = "product_variants"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_product_variants_price_not_negative"),
        CheckConstraint("base_quantity > 0", name="ck_product_variants_base_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(20))
    price: Mapped[float] = mapped_column(Money)
    base_quantity: Mapped[float] = mapped_column(Quantity, default=1, server_default="1")
    is_active: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    product: Mapped["Product"] = relationship(back_populates="variants")

    @property
    def stock_quantity(self) -> float:
        """Сколько единиц этого варианта можно продать из общего склада."""
        stock = self.product.stock_quantity if self.product else 0

        if self.base_quantity == 1:
            return stock

        return math.floor(stock / self.base_quantity + 1e-9)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(one_of("status", ORDER_STATUSES), name="ck_orders_status"),
        CheckConstraint(one_of("delivery_method", DELIVERY_METHODS), name="ck_orders_delivery_method"),
        CheckConstraint("total_price >= 0", name="ck_orders_total_not_negative"),
        # «Мои заказы»: WHERE user_id = … ORDER BY id DESC LIMIT 20 — индекс
        # сразу отдаёт последние заказы покупателя (один user_id не помогал)
        Index("ix_orders_user_id_id", "user_id", "id"),
        # Счётчик новых заказов, этапы и отчёты: фильтр по статусу + период
        Index("ix_orders_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(50), default="NEW")
    total_price: Mapped[float] = mapped_column(Money, default=0)
    delivery_address: Mapped[str] = mapped_column(String(500))
    # DELIVERY — привозит магазин, PICKUP — самовывоз со склада
    delivery_method: Mapped[str] = mapped_column(String(20), default="DELIVERY", server_default="DELIVERY")
    customer_name: Mapped[str] = mapped_column(String(255), default="Покупатель")
    # «Распилить по 3 м», «привезти после 14:00» — от покупателя
    comment: Mapped[str | None] = mapped_column(String(500))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # Когда оформлен заказ — для отчётов и сортировки (раньше брали из истории статусов)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    user: Mapped["User"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.id",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )

    @property
    def customer_phone(self) -> str | None:
        return self.user.phone if self.user else None



@event.listens_for(Session, "before_flush")
def ensure_default_variant(session, flush_context, instances):
    """У каждого нового товара должен быть хотя бы один вариант."""
    for obj in list(session.new):
        if isinstance(obj, Product) and not obj.variants:
            obj.variants.append(
                ProductVariant(
                    name=obj.unit,
                    unit=obj.unit,
                    price=obj.price,
                    base_quantity=1,
                    is_active=1,
                )
            )

class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint("price >= 0", name="ck_order_items_price_not_negative"),
        CheckConstraint("base_quantity > 0", name="ck_order_items_base_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", name="fk_order_items_variant_id_product_variants"),
    )
    quantity: Mapped[float] = mapped_column(Quantity)
    price: Mapped[float] = mapped_column(Money)
    unit: Mapped[str] = mapped_column(String(20))
    # Сколько базовых единиц списано за 1 единицу (снимок на момент заказа)
    base_quantity: Mapped[float] = mapped_column(Quantity, default=1, server_default="1")

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="order_items")
    variant: Mapped["ProductVariant"] = relationship()

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def variant_name(self) -> str | None:
        return self.variant.name if self.variant else None


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    # Кто сменил статус: покупатель (оформил, отменил) или администратор.
    # Пусто — у записей, сделанных до появления журнала
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    order: Mapped["Order"] = relationship(back_populates="status_history")
    changed_by: Mapped["User | None"] = relationship()

    @property
    def changed_by_label(self) -> str | None:
        """«Админ admin@…» или «Покупатель +7999…» — для журнала."""
        user = self.changed_by
        if user is None:
            return None
        role = "Админ" if user.role == "ADMIN" else "Покупатель"
        return f"{role} {user.email or user.phone or f'№{user.id}'}"


class Notification(Base):
    __tablename__ = "notifications"
    # Колокольчик: непрочитанные уведомления покупателя
    __table_args__ = (Index("ix_notifications_user_id_is_read", "user_id", "is_read"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    status: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(String(500))
    is_read: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    user: Mapped["User"] = relationship(back_populates="notifications")
    order: Mapped["Order"] = relationship(back_populates="notifications")


class TelegramAccountLink(Base):
    __tablename__ = "telegram_account_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    user: Mapped["User"] = relationship()


class PasswordResetCode(Base):
    """Одноразовый код сброса пароля, который бот присылает в Telegram.

    Хранится только хеш кода; у пользователя один активный код — новый
    запрос заменяет старый. Код живёт 10 минут и даёт 5 попыток.
    """

    __tablename__ = "password_reset_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


OUTBOX_STATUSES = ("pending", "sent", "failed")


class OutboxMessage(Base):
    """Сообщение в Telegram, записанное в той же транзакции, что и заказ.

    Если процесс упадёт между сохранением заказа и отправкой, сообщение не
    потеряется: его отправит следующий проход (API сразу после ответа, бот —
    раз в несколько секунд). Неудачные попытки повторяются с паузой.
    """

    __tablename__ = "telegram_outbox"
    __table_args__ = (
        CheckConstraint(one_of("status", OUTBOX_STATUSES), name="ck_telegram_outbox_status"),
        # Отправитель выбирает ждущие сообщения, у которых подошло время
        Index("ix_telegram_outbox_status_next_attempt_at", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    reply_markup: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    """Журнал действий в админке: кто и когда менял товары, варианты,
    категории, администраторов и пароли покупателей.

    Записывается в той же транзакции, что и само изменение. Статусы
    заказов ведёт отдельная история — order_status_history.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_entity", "entity", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(50))
    entity: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    # По-человечески: «Доска 50×150: цена 600 → 650 ₽; остаток 100 → 120 шт»
    summary: Mapped[str] = mapped_column(String(500))
    # Было/стало по полям — для разбора спорных случаев
    changes: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    actor: Mapped["User | None"] = relationship()

    @property
    def actor_label(self) -> str | None:
        user = self.actor
        if user is None:
            return None
        return user.email or user.phone or f"№{user.id}"



CALLBACK_STATUSES = ("NEW", "DONE")


class CallbackRequest(Base):
    """Заявка «перезвоните мне» — заказ по телефону, без регистрации и пароля.

    Состав корзины сохраняется текстом по ценам на момент заявки: менеджер
    видит, что человек хотел, и оформляет заказ во время звонка.
    """

    __tablename__ = "callback_requests"
    __table_args__ = (
        CheckConstraint(one_of("status", CALLBACK_STATUSES), name="ck_callback_requests_status"),
        Index("ix_callback_requests_status_id", "status", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str | None] = mapped_column(String(500))
    cart_summary: Mapped[str | None] = mapped_column(Text)
    cart_total: Mapped[float | None] = mapped_column(Money)
    status: Mapped[str] = mapped_column(String(10), default="NEW", server_default="NEW")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    handled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)

    handled_by: Mapped["User | None"] = relationship()

    @property
    def handled_by_label(self) -> str | None:
        user = self.handled_by
        if user is None:
            return None
        return user.email or user.phone or f"№{user.id}"


@event.listens_for(Base.metadata, "before_create")
def create_trgm_extension(target, connection, **kwargs):
    """Без расширения не создастся триграммный индекс (новая база, тесты)."""
    connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
