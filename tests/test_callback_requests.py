"""Заявка «перезвоните мне»: без регистрации, с корзиной, сообщение админам."""

from fastapi.testclient import TestClient
from test_bot_handlers import ADMIN_TG, press, sent  # noqa: F401

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import AuditLog, CallbackRequest, Category, OutboxMessage, Product, TelegramAccountLink, User
from bot import handlers


def make_admin(telegram=True):
    db = SessionLocal()
    admin = User(email="admin@woodcommerce.local", password_hash=hash_password("x" * 8), role="ADMIN")
    db.add(admin)
    db.flush()
    if telegram:
        db.add(TelegramAccountLink(user_id=admin.id, telegram_user_id=ADMIN_TG, telegram_chat_id=ADMIN_TG))
    db.commit()
    admin_id = admin.id
    db.close()
    return admin_id


def make_variant(price=620):
    db = SessionLocal()
    category = Category(name="Доска")
    db.add(category)
    db.flush()
    product = Product(
        name="Доска 50×150", price=price, stock_quantity=100, unit="шт", category_id=category.id, is_active=1
    )
    db.add(product)
    db.commit()
    variant_id = product.variants[0].id
    db.close()
    return variant_id


def body(**fields):
    return {"name": "Сергей", "phone": "8 (999) 111-22-33", "privacy_accepted": True, **fields}


def test_request_without_account_reaches_admins(client: TestClient):
    make_admin()
    variant_id = make_variant()

    response = client.post(
        "/api/v1/callback-requests/",
        json=body(comment="нужен распил", items=[{"variant_id": variant_id, "quantity": 3}]),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "+79991112233"
    assert data["cart_total"] == 1860
    assert "Доска 50×150 — 3 шт" in data["cart_summary"]
    db = SessionLocal()
    message = db.query(OutboxMessage).one()
    db.close()
    assert message.chat_id == ADMIN_TG
    assert "+79991112233" in message.text and "нужен распил" in message.text
    assert message.reply_markup["inline_keyboard"][0][0]["callback_data"] == f"cb:done:{data['id']}"


def test_prices_come_from_database_not_from_browser(client: TestClient):
    variant_id = make_variant(price=620)

    data = client.post(
        "/api/v1/callback-requests/",
        json=body(items=[{"variant_id": variant_id, "quantity": 1, "price": 1}, {"variant_id": 999999, "quantity": 5}]),
    ).json()

    assert data["cart_total"] == 620
    assert "999999" not in (data["cart_summary"] or "")


def test_consent_and_real_phone_are_required(client: TestClient):
    assert client.post("/api/v1/callback-requests/", json=body(privacy_accepted=False)).status_code == 422
    assert client.post("/api/v1/callback-requests/", json=body(phone="12345678901234")).status_code == 422


def test_requests_are_rate_limited(client: TestClient):
    for _ in range(5):
        assert client.post("/api/v1/callback-requests/", json=body()).status_code == 200
    assert client.post("/api/v1/callback-requests/", json=body()).status_code == 429


def test_only_admin_sees_and_closes_requests(client: TestClient):
    admin_id = make_admin(telegram=False)
    request_id = client.post("/api/v1/callback-requests/", json=body()).json()["id"]
    admin = {"Authorization": f"Bearer {create_access_token(user_id=admin_id, role='ADMIN')}"}

    assert client.get("/api/v1/callback-requests/").status_code == 401
    new = client.get("/api/v1/callback-requests/?status=NEW", headers=admin).json()
    assert [item["id"] for item in new] == [request_id]

    done = client.post(f"/api/v1/callback-requests/{request_id}/done", headers=admin).json()
    assert done["status"] == "DONE" and done["handled_by_label"] == "admin@woodcommerce.local"
    assert client.get("/api/v1/callback-requests/?status=NEW", headers=admin).json() == []
    db = SessionLocal()
    assert db.query(AuditLog).filter(AuditLog.action == "callback.done").count() == 1
    db.close()


def test_bot_button_marks_request_done(client: TestClient, sent):  # noqa: F811
    make_admin()
    request_id = client.post("/api/v1/callback-requests/", json=body()).json()["id"]

    handlers.handle_callback(press(f"cb:done:{request_id}", ADMIN_TG))

    db = SessionLocal()
    assert db.get(CallbackRequest, request_id).status == "DONE"
    db.close()
    edits = [payload for method, payload in sent if method == "editMessageText"]
    assert "Перезвонили" in edits[-1]["text"]
