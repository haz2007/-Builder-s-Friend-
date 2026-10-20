import pytest
from sqlalchemy.exc import IntegrityError

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Category, Order, Product, User
from app.rate_limit import RateLimiter, telegram_login_limiter


def test_short_password_is_rejected_on_register(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"phone": "+79991110010", "password": "1234567"},
    )

    assert response.status_code == 422


def test_old_short_password_still_logs_in(client):
    """Ограничение — только для новых паролей: старые аккаунты не блокируются."""
    db = SessionLocal()
    db.add(User(phone="+79991110011", password_hash=hash_password("123"), role="CUSTOMER"))
    db.commit()
    db.close()

    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "+79991110011", "password": "123"},
    )

    assert response.status_code == 200


def test_login_attempts_are_limited(client):
    for _ in range(10):
        response = client.post(
            "/api/v1/auth/login",
            json={"phone": "+79991110012", "password": "wrong-password"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "+79991110012", "password": "wrong-password"},
    )

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "Слишком много попыток" in response.json()["detail"]


def test_registrations_are_limited(client):
    for index in range(5):
        response = client.post(
            "/api/v1/auth/register",
            json={"phone": f"+7999111002{index}", "password": "12345678"},
        )
        assert response.status_code == 200

    response = client.post(
        "/api/v1/auth/register",
        json={"phone": "+79991110029", "password": "12345678"},
    )

    assert response.status_code == 429


def test_limiter_window_and_keys(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.rate_limit.time.monotonic", lambda: now[0])
    limiter = RateLimiter("test", limit=2, window=60)

    assert limiter.hit("a") is None
    assert limiter.hit("a") is None
    assert limiter.hit("a") == 61
    # У другого ключа свой счётчик
    assert limiter.hit("b") is None

    now[0] += 61
    assert limiter.hit("a") is None


def test_telegram_login_is_limited_per_user():
    for _ in range(5):
        assert telegram_login_limiter.hit("42") is None

    assert telegram_login_limiter.hit("42") is not None
    assert telegram_login_limiter.hit("43") is None


def make_product(db) -> Product:
    category = Category(name="Доска")
    db.add(category)
    db.flush()
    product = Product(
        name="Доска",
        price=100,
        stock_quantity=5,
        unit="шт",
        category_id=category.id,
        is_active=1,
    )
    db.add(product)
    db.commit()
    return product


def test_database_rejects_negative_stock(reset_database):
    db = SessionLocal()
    product = make_product(db)

    product.stock_quantity = -1
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


@pytest.mark.parametrize("field, value", [("status", "LOST"), ("delivery_method", "DRONE")])
def test_database_rejects_unknown_order_values(reset_database, field, value):
    db = SessionLocal()
    user = User(phone="+79991110030", password_hash="x", role="CUSTOMER")
    db.add(user)
    db.flush()
    order = Order(customer_name="Тест", delivery_address="Москва", user_id=user.id)
    setattr(order, field, value)
    db.add(order)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_database_rejects_removed_driver_role(reset_database):
    db = SessionLocal()
    db.add(User(phone="+79991110031", password_hash="x", role="DRIVER"))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()
