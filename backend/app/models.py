
import math
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    BigInteger,
    CheckConstraint,
    Table,
)
from sqlalchemy import event
from sqlalchemy.orm import Session, relationship

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
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=True, unique=True)
    phone = Column(String(30), nullable=True, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="CUSTOMER")
    # Владелец магазина: администратор, который управляет другими админами
    is_owner = Column(Integer, nullable=False, default=0, server_default="0")

    orders = relationship("Order", back_populates="user")
    notifications = relationship(
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
)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    # Подкатегория указывает на родителя: «Доска» → «Пиломатериалы»
    parent_id = Column(
        Integer,
        ForeignKey(
            "categories.id",
            ondelete="SET NULL",
            name="fk_categories_parent_id_categories",
        ),
        nullable=True,
        index=True,
    )

    products = relationship("Product", back_populates="category")
    parent = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship("Category", back_populates="parent", order_by="Category.name")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_not_negative"),
        CheckConstraint("price >= 0", name="ck_products_price_not_negative"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000))
    price = Column(Float, nullable=False)
    # Общий остаток товара в базовой единице unit (для досок — в штуках)
    stock_quantity = Column(Float, nullable=False, default=0)
    unit = Column(String(20), nullable=False)

    # Размеры доски в мм; если заданы, остаток ведётся в штуках
    thickness_mm = Column(Float, nullable=True)
    width_mm = Column(Float, nullable=True)
    length_mm = Column(Float, nullable=True)

    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
        nullable=False,
    )

    is_active = Column(Integer, nullable=False, default=1)
    image_url = Column(String(500), nullable=True)

    category = relationship("Category", back_populates="products")
    categories = relationship("Category", secondary=product_categories)
    order_items = relationship("OrderItem", back_populates="product")
    variants = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductVariant.id",
    )

    @property
    def category_ids(self):
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

    id = Column(Integer, primary_key=True)
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    unit = Column(String(20), nullable=False)
    price = Column(Float, nullable=False)
    base_quantity = Column(
        Float,
        nullable=False,
        default=1,
        server_default="1",
    )
    is_active = Column(Integer, nullable=False, default=1, server_default="1")

    product = relationship("Product", back_populates="variants")

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
    )

    id = Column(Integer, primary_key=True)
    status = Column(String(50), nullable=False, default="NEW")
    total_price = Column(Float, nullable=False, default=0)
    delivery_address = Column(String(500), nullable=False)
    # DELIVERY — привозит магазин, PICKUP — самовывоз со склада
    delivery_method = Column(
        String(20),
        nullable=False,
        default="DELIVERY",
        server_default="DELIVERY",
    )
    customer_name = Column(
        String(100),
        nullable=False,
        default="Покупатель",
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="orders")

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    status_history = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.id",
    )

    notifications = relationship(
        "Notification",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    @property
    def customer_phone(self):
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

    id = Column(Integer, primary_key=True)
    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
    )
    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False,
    )
    variant_id = Column(
        Integer,
        ForeignKey(
            "product_variants.id",
            name="fk_order_items_variant_id_product_variants",
        ),
        nullable=False,
    )
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    # Сколько базовых единиц списано за 1 единицу (снимок на момент заказа)
    base_quantity = Column(
        Float,
        nullable=False,
        default=1,
        server_default="1",
    )

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    variant = relationship("ProductVariant")

    @property
    def product_name(self):
        return self.product.name if self.product else None

    @property
    def variant_name(self):
        return self.variant.name if self.variant else None


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True)
    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
    )
    status = Column(String(50), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    order = relationship("Order", back_populates="status_history")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
    )
    status = Column(String(50), nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="notifications")
    order = relationship("Order", back_populates="notifications")


class TelegramAccountLink(Base):
    __tablename__ = "telegram_account_links"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    telegram_user_id = Column(
        BigInteger,
        nullable=False,
        unique=True,
    )

    telegram_chat_id = Column(
        BigInteger,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User")
