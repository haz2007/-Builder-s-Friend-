from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, TelegramAccountLink, User
from app.services import order_notifications

FLOW = ["CONFIRMED", "PREPARING", "READY_FOR_DELIVERY", "ASSIGNED_TO_DRIVER", "ON_THE_WAY"]


def create_user(role, **fields):
    db = SessionLocal()
    user = User(password_hash=hash_password("password123"), role=role, **fields)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def headers(user):
    token = create_access_token(user_id=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def link(user, telegram_id):
    db = SessionLocal()
    db.add(TelegramAccountLink(
        user_id=user.id,
        telegram_user_id=telegram_id,
        telegram_chat_id=telegram_id,
    ))
    db.commit()
    db.close()


def make_order(client, customer, method="DELIVERY"):
    db = SessionLocal()
    category = Category(name="Пиломатериалы")
    db.add(category)
    db.commit()
    product = Product(name="Брус", price=900, stock_quantity=20, unit="шт", category_id=category.id)
    db.add(product)
    db.commit()
    product_id = product.id
    db.close()

    return client.post(
        "/api/v1/orders/",
        json={
            "customer_name": "Покупатель",
            "delivery_method": method,
            "delivery_address": "Химки, улица Строителей, 1",
            "items": [{"product_id": product_id, "quantity": 2}],
        },
        headers=headers(customer),
    ).json()["id"]


def capture(monkeypatch):
    sent = []
    monkeypatch.setattr(
        order_notifications,
        "send_telegram_message",
        lambda chat_id, text, markup=None: sent.append((chat_id, text, markup)) or True,
    )
    return sent


def set_status(client, admin, order_id, status):
    return client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": status},
        headers=headers(admin),
    )


def review_messages(sent):
    return [
        (chat_id, text, markup)
        for chat_id, text, markup in sent
        if markup and "Оставить отзыв" in str(markup)
    ]


def test_review_request_after_delivery(client: TestClient, monkeypatch):
    customer = create_user("CUSTOMER", phone="+79990001122")
    admin = create_user("ADMIN", email="admin@woodcommerce.local")
    link(customer, 1001)
    link(admin, 2002)
    order_id = make_order(client, customer)
    sent = capture(monkeypatch)

    for status in FLOW:
        set_status(client, admin, order_id, status)
    assert review_messages(sent) == []

    set_status(client, admin, order_id, "DELIVERED")

    reviews = review_messages(sent)
    assert len(reviews) == 1
    chat_id, text, markup = reviews[0]
    assert chat_id == 1001
    assert "доставлен" in text
    assert "add-review=true" in markup["inline_keyboard"][0][0]["url"]


def test_pickup_order_says_issued(client: TestClient, monkeypatch):
    customer = create_user("CUSTOMER", phone="+79990001122")
    admin = create_user("ADMIN", email="admin@woodcommerce.local")
    link(customer, 1001)
    order_id = make_order(client, customer, method="PICKUP")
    for status in FLOW:
        set_status(client, admin, order_id, status)
    sent = capture(monkeypatch)

    set_status(client, admin, order_id, "DELIVERED")

    assert "выдан" in review_messages(sent)[0][1]


def test_no_review_request_without_bot_login(client: TestClient, monkeypatch):
    customer = create_user("CUSTOMER", phone="+79990001122")
    admin = create_user("ADMIN", email="admin@woodcommerce.local")
    order_id = make_order(client, customer)
    for status in FLOW:
        set_status(client, admin, order_id, status)
    sent = capture(monkeypatch)

    set_status(client, admin, order_id, "DELIVERED")

    assert review_messages(sent) == []
