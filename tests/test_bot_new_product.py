"""Новый товар и фото из Telegram-бота: диалог по шагам, фото сжимается."""

import io

import pytest
from PIL import Image
from test_bot_handlers import ADMIN_TG, CUSTOMER_TG, make_user, message, press, sent  # noqa: F401

from app.database import SessionLocal
from app.models import AuditLog, Category, Product
from app.routers import products as products_router
from bot import handlers, new_product


@pytest.fixture
def admin(sent, tmp_path, monkeypatch):  # noqa: F811
    make_user("ADMIN", telegram_id=ADMIN_TG, email="admin@woodcommerce.local")
    monkeypatch.setattr(products_router, "UPLOAD_DIR", tmp_path)
    return sent


@pytest.fixture
def telegram_photo(monkeypatch):
    """Подменяет скачивание файла из Telegram: «телефонный» снимок 3000×2000."""
    data = io.BytesIO()
    Image.new("RGB", (3000, 2000), (150, 100, 50)).save(data, "JPEG")
    monkeypatch.setattr(new_product, "download_photo", lambda msg: data.getvalue())


def make_category():
    db = SessionLocal()
    category = Category(name="Брус")
    db.add(category)
    db.commit()
    category_id = category.id
    db.close()
    return category_id


def photo_message():
    return {**message("", ADMIN_TG), "photo": [{"file_id": "small"}, {"file_id": "big"}]}


def fill_until_photo(category_id):
    handlers.handle_callback(press("a:new", ADMIN_TG))
    handlers.handle_message(message("Брус 150×150×6000", ADMIN_TG))
    handlers.handle_callback(press(f"a:newcat:{category_id}", ADMIN_TG))
    handlers.handle_callback(press("a:newunit:0", ADMIN_TG))  # шт
    handlers.handle_message(message("1 850", ADMIN_TG))
    handlers.handle_message(message("40", ADMIN_TG))


def test_admin_adds_product_with_photo(admin, telegram_photo, tmp_path):
    category_id = make_category()

    fill_until_photo(category_id)
    handlers.handle_message(photo_message())

    db = SessionLocal()
    product = db.query(Product).one()
    entry = db.query(AuditLog).filter(AuditLog.action == "product.created").one()
    assert (product.name, product.price, product.stock_quantity, product.unit) == ("Брус 150×150×6000", 1850, 40, "шт")
    assert product.category_id == category_id and product.is_active == 1
    assert product.variants[0].price == 1850
    db.close()
    assert "(Telegram)" in entry.summary
    saved = next(tmp_path.iterdir())
    assert product.image_url == f"/uploads/products/{saved.name}"
    with Image.open(saved) as image:
        assert image.format == "WEBP" and max(image.size) == 1600


def test_product_can_be_saved_without_photo(admin):
    fill_until_photo(make_category())
    handlers.handle_callback(press("a:newsave", ADMIN_TG))

    db = SessionLocal()
    assert db.query(Product).one().image_url is None
    db.close()


def test_wrong_price_and_fractional_pieces_are_asked_again(admin):
    handlers.handle_callback(press("a:new", ADMIN_TG))
    handlers.handle_message(message("Брус", ADMIN_TG))
    handlers.handle_callback(press(f"a:newcat:{make_category()}", ADMIN_TG))
    handlers.handle_callback(press("a:newunit:0", ADMIN_TG))
    handlers.handle_message(message("дорого", ADMIN_TG))
    handlers.handle_message(message("900", ADMIN_TG))
    handlers.handle_message(message("2,5", ADMIN_TG))

    texts = [payload["text"] for _, payload in admin if "text" in payload]
    assert any("Нужна цена числом" in text for text in texts)
    assert any("для штук — целым" in text for text in texts)


def test_admin_replaces_photo_of_existing_product(admin, telegram_photo):
    fill_until_photo(make_category())
    handlers.handle_callback(press("a:newsave", ADMIN_TG))
    db = SessionLocal()
    product_id = db.query(Product).one().id
    db.close()

    handlers.handle_callback(press(f"a:photo:{product_id}", ADMIN_TG))
    handlers.handle_message(photo_message())

    db = SessionLocal()
    assert db.get(Product, product_id).image_url.endswith(".webp")
    db.close()


def test_customer_cannot_add_products(sent):  # noqa: F811
    make_user("CUSTOMER", telegram_id=CUSTOMER_TG, phone="+79991230010")

    handlers.handle_callback(press("a:new", CUSTOMER_TG))
    handlers.handle_message(message("Брус", CUSTOMER_TG))

    db = SessionLocal()
    assert db.query(Product).count() == 0
    db.close()
