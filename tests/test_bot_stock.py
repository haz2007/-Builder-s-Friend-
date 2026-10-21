"""Склад в Telegram-боте: поиск товара, остаток «+20/-3/150» и цена."""

import pytest
from test_bot_handlers import ADMIN_TG, CUSTOMER_TG, make_user, message, press, sent, texts  # noqa: F401

from app.database import SessionLocal
from app.models import AuditLog, Category, Product, ProductVariant
from bot import handlers
from bot.stock import parse_number


def make_product(stock=10, unit="шт"):
    db = SessionLocal()
    category = Category(name="Брус")
    db.add(category)
    db.flush()
    product = Product(name="Брус 100х100", price=900, stock_quantity=stock, unit=unit,
                      category_id=category.id, is_active=1)
    db.add(product)
    # Основной вариант создаётся сам (ensure_default_variant)
    db.commit()
    ids = product.id, product.variants[0].id
    db.close()
    return ids


@pytest.fixture
def admin(sent):  # noqa: F811
    make_user("ADMIN", telegram_id=ADMIN_TG, email="admin@woodcommerce.local")
    return sent


def stock_of(product_id):
    db = SessionLocal()
    value = db.get(Product, product_id).stock_quantity
    db.close()
    return value


@pytest.mark.parametrize(
    ("text", "expected"),
    [("+20", ("+", 20)), ("-3,5", ("-", 3.5)), ("1 200", ("=", 1200)), ("abc", None), ("2+2", None)],
)
def test_parse_number(text, expected):
    parsed = parse_number(text)
    assert (parsed and (parsed[0], float(parsed[1]))) == expected


def test_admin_adds_and_writes_off_stock(admin):
    product_id, _ = make_product(stock=10)

    handlers.handle_callback(press(f"a:setstock:{product_id}", ADMIN_TG))
    handlers.handle_message(message("+20", ADMIN_TG))
    assert stock_of(product_id) == 30

    handlers.handle_callback(press(f"a:setstock:{product_id}", ADMIN_TG))
    handlers.handle_message(message("-5", ADMIN_TG))
    assert stock_of(product_id) == 25

    db = SessionLocal()
    entries = db.query(AuditLog).filter(AuditLog.action == "product.stock").order_by(AuditLog.id).all()
    db.close()
    assert [entry.changes["stock_quantity"] for entry in entries] == [[10, 30], [30, 25]]
    assert "(Telegram)" in entries[0].summary


def test_stock_cannot_go_negative_or_fractional_for_pieces(admin):
    product_id, _ = make_product(stock=2)

    handlers.handle_callback(press(f"a:setstock:{product_id}", ADMIN_TG))
    handlers.handle_message(message("-5", ADMIN_TG))
    handlers.handle_message(message("1,5", ADMIN_TG))

    assert stock_of(product_id) == 2
    assert any("Столько нет" in text for text in texts(admin))
    assert any("целое число" in text for text in texts(admin))


def test_admin_changes_price(admin):
    product_id, variant_id = make_product()

    handlers.handle_callback(press(f"a:setprice:{variant_id}", ADMIN_TG))
    handlers.handle_message(message("950", ADMIN_TG))

    db = SessionLocal()
    variant_price = db.get(ProductVariant, variant_id).price
    product_price = db.get(Product, product_id).price
    db.close()
    assert variant_price == 950
    # Цена в каталоге — это цена основного варианта
    assert product_price == 950


def test_search_finds_product_by_size(admin):
    product_id, _ = make_product()

    handlers.handle_callback(press("a:find", ADMIN_TG))
    handlers.handle_message(message("брусок 100x100", ADMIN_TG))
    handlers.handle_message(message("брус 100x100", ADMIN_TG))

    keyboards = [payload["reply_markup"] for _, payload in admin if "reply_markup" in payload]
    callbacks = [button.get("callback_data") for row in keyboards[-1]["inline_keyboard"] for button in row]
    assert f"a:prod:{product_id}" in callbacks


def test_other_button_cancels_waiting_for_number(admin):
    product_id, _ = make_product(stock=10)

    handlers.handle_callback(press(f"a:setstock:{product_id}", ADMIN_TG))
    handlers.handle_callback(press("home", ADMIN_TG))
    handlers.handle_message(message("+20", ADMIN_TG))

    assert stock_of(product_id) == 10


def test_customer_cannot_change_stock(sent):  # noqa: F811
    make_user("CUSTOMER", telegram_id=CUSTOMER_TG, phone="+79991230009")
    product_id, _ = make_product(stock=10)

    handlers.handle_callback(press(f"a:setstock:{product_id}", CUSTOMER_TG))
    handlers.handle_message(message("+20", CUSTOMER_TG))

    assert stock_of(product_id) == 10
