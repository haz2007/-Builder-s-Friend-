from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="CUSTOMER")

    orders = relationship("Order", back_populates="user")

    deliveries = relationship(
        "Delivery",
        back_populates="driver"
    )


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000))
    price = Column(Float, nullable=False)
    stock_quantity = Column(Float, nullable=False, default=0)
    unit = Column(String(20), nullable=False)

    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
        nullable=False
    )

    category = relationship(
        "Category",
        back_populates="products"
    )

    order_items = relationship(
        "OrderItem",
        back_populates="product"
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    status = Column(
        String(50),
        nullable=False,
        default="NEW"
    )
    total_price = Column(
        Float,
        nullable=False,
        default=0
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    user = relationship(
        "User",
        back_populates="orders"
    )

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    delivery = relationship(
        "Delivery",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False
    )

    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)

    order = relationship(
        "Order",
        back_populates="items"
    )

    product = relationship(
        "Product",
        back_populates="order_items"
    )


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True)

    status = Column(
        String(50),
        nullable=False,
        default="WAITING"
    )

    address = Column(
        String(500),
        nullable=False
    )

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
        unique=True
    )

    driver_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    order = relationship(
        "Order",
        back_populates="delivery"
    )

    driver = relationship(
        "User",
        back_populates="deliveries"
    )