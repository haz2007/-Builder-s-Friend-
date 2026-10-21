"""Самовывоз («Готов к выдаче» → «Выдан»), журнал действий и согласие с политикой."""

from fastapi.testclient import TestClient
from test_admin_analytics_v2 import order, setup_shop

from app.database import SessionLocal
from app.models import User
from app.services.order_notifications import build_order_keyboard, status_name


def set_status(client, admin, order_id, status):
    return client.patch(f"/api/v1/orders/{order_id}/status", json={"status": status}, headers=admin)


def test_pickup_skips_on_the_way(client: TestClient):
    admin, customer, product_id = setup_shop()
    order_id = order(client, customer, product_id, 1)["id"]
    for status in ["CONFIRMED", "PREPARING"]:
        set_status(client, admin, order_id, status)

    ready = set_status(client, admin, order_id, "READY_FOR_DELIVERY").json()

    assert ready["allowed_statuses"] == ["DELIVERED", "CANCELLED"]
    assert set_status(client, admin, order_id, "ON_THE_WAY").status_code == 400
    assert set_status(client, admin, order_id, "DELIVERED").json()["status"] == "DELIVERED"


def test_delivery_still_goes_on_the_way(client: TestClient):
    admin, customer, product_id = setup_shop()
    order_id = order(client, customer, product_id, 1, method="DELIVERY")["id"]
    for status in ["CONFIRMED", "PREPARING"]:
        set_status(client, admin, order_id, status)

    ready = set_status(client, admin, order_id, "READY_FOR_DELIVERY").json()

    assert ready["allowed_statuses"] == ["ON_THE_WAY", "CANCELLED"]
    assert set_status(client, admin, order_id, "DELIVERED").status_code == 400


def test_pickup_names_and_bot_buttons():
    assert status_name("READY_FOR_DELIVERY", "PICKUP") == "Готов к выдаче"
    assert status_name("DELIVERED", "PICKUP") == "Выдан"
    assert status_name("DELIVERED", "DELIVERY") == "Доставлен"

    buttons = build_order_keyboard(7, "READY_FOR_DELIVERY", "PICKUP")["inline_keyboard"]
    assert [row[0]["callback_data"] for row in buttons] == ["order:7:DELIVERED", "order:7:CANCELLED"]
    assert buttons[0][0]["text"] == "🤝 Выдан покупателю"


def test_history_records_who_changed_status(client: TestClient):
    admin, customer, product_id = setup_shop()
    order_id = order(client, customer, product_id, 1)["id"]

    data = set_status(client, admin, order_id, "CONFIRMED").json()

    by_status = {entry["status"]: entry["changed_by"] for entry in data["status_history"]}
    assert by_status["NEW"] == "Покупатель +79990001122"
    assert by_status["CONFIRMED"] == "Админ admin@woodcommerce.local"


def test_customer_cancel_is_logged_as_customer(client: TestClient):
    _, customer, product_id = setup_shop()
    order_id = order(client, customer, product_id, 1)["id"]

    data = client.post(f"/api/v1/orders/{order_id}/cancel", headers=customer).json()

    assert data["status_history"][-1]["changed_by"] == "Покупатель +79990001122"


def test_activity_log_for_admins_only(client: TestClient):
    admin, customer, product_id = setup_shop()
    order_id = order(client, customer, product_id, 1)["id"]
    for status in ["CONFIRMED", "PREPARING", "READY_FOR_DELIVERY"]:
        set_status(client, admin, order_id, status)

    entries = client.get("/api/v1/admin/activity", headers=admin).json()

    assert [entry["status"] for entry in entries][:2] == ["READY_FOR_DELIVERY", "PREPARING"]
    assert entries[0]["status_name"] == "Готов к выдаче"
    assert entries[0]["changed_by"] == "Админ admin@woodcommerce.local"
    assert client.get("/api/v1/admin/activity", headers=customer).status_code == 403


def test_register_requires_privacy_consent(client: TestClient):
    response = client.post(
        "/api/v1/auth/register", json={"phone": "+79991230001", "password": "12345678"}
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/auth/register",
        json={"phone": "+79991230001", "password": "12345678", "privacy_accepted": False},
    )
    assert response.status_code == 422


def test_consent_time_is_saved(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"phone": "+79991230002", "password": "12345678", "privacy_accepted": True},
    )

    db = SessionLocal()
    user = db.query(User).filter(User.id == response.json()["id"]).first()
    assert user.privacy_accepted_at is not None
    db.close()


def test_times_are_sent_as_utc(client: TestClient):
    """Без пометки UTC браузер показывал время заказа на 3 часа раньше."""
    admin, customer, product_id = setup_shop()
    data = order(client, customer, product_id, 1)

    assert data["status_history"][0]["created_at"].endswith("+00:00")
    assert client.get("/api/v1/admin/activity", headers=admin).json()[0]["created_at"].endswith("+00:00")
