from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, TelegramAccountLink, User
from app.services import order_notifications


def create_user(role="CUSTOMER", is_owner=0, **fields):
    db = SessionLocal()
    user = User(
        password_hash=hash_password("password123"),
        role=role,
        is_owner=is_owner,
        **fields,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def headers(user):
    token = create_access_token(user_id=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def link_telegram(user, telegram_id):
    db = SessionLocal()
    db.add(TelegramAccountLink(
        user_id=user.id,
        telegram_user_id=telegram_id,
        telegram_chat_id=telegram_id,
    ))
    db.commit()
    db.close()


def test_owner_adds_admin_by_phone(client: TestClient):
    owner = create_user("ADMIN", 1, email="owner@woodcommerce.local")
    create_user(phone="+79991112233")

    response = client.post(
        "/api/v1/admins/",
        json={"login": "8 999 111-22-33"},
        headers=headers(owner),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"


def test_regular_admin_cannot_add_admins(client: TestClient):
    admin = create_user("ADMIN", email="admin@woodcommerce.local")
    create_user(phone="+79991112233")

    response = client.post(
        "/api/v1/admins/",
        json={"login": "+79991112233"},
        headers=headers(admin),
    )

    assert response.status_code == 403


def test_regular_admin_cannot_promote_via_role_endpoint(client: TestClient):
    admin = create_user("ADMIN", email="admin@woodcommerce.local")
    customer = create_user(phone="+79991112233")

    response = client.patch(
        f"/api/v1/users/{customer.id}/role?role=ADMIN",
        headers=headers(admin),
    )

    assert response.status_code == 403


def test_owner_cannot_be_removed(client: TestClient):
    owner = create_user("ADMIN", 1, email="owner@woodcommerce.local")

    response = client.delete(
        f"/api/v1/admins/{owner.id}",
        headers=headers(owner),
    )

    assert response.status_code == 400


def test_owner_removes_admin(client: TestClient):
    owner = create_user("ADMIN", 1, email="owner@woodcommerce.local")
    admin = create_user("ADMIN", phone="+79991112233")

    response = client.delete(f"/api/v1/admins/{admin.id}", headers=headers(owner))

    assert response.status_code == 200
    assert response.json()["role"] == "CUSTOMER"


def test_add_unknown_user_gives_clear_error(client: TestClient):
    owner = create_user("ADMIN", 1, email="owner@woodcommerce.local")

    response = client.post(
        "/api/v1/admins/",
        json={"login": "+79990000000"},
        headers=headers(owner),
    )

    assert response.status_code == 400
    assert "зарегистрируется" in response.json()["detail"]


def make_order(client, customer):
    db = SessionLocal()
    category = Category(name="Крепёж")
    db.add(category)
    db.commit()
    product = Product(
        name="Саморез",
        price=100,
        stock_quantity=50,
        unit="кг",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    product_id = product.id
    db.close()

    return client.post(
        "/api/v1/orders/",
        json={
            "customer_name": "Покупатель",
            "delivery_address": "Москва, улица Ленина, 1",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
        headers=headers(customer),
    ).json()["id"]


def capture_messages(monkeypatch):
    sent = []
    monkeypatch.setattr(
        order_notifications,
        "send_telegram_message",
        lambda chat_id, text, markup=None: sent.append(chat_id) or True,
    )
    return sent


def test_new_order_goes_to_linked_customer_and_admins(client, monkeypatch):
    sent = capture_messages(monkeypatch)
    customer = create_user(phone="+79991112233")
    admin = create_user("ADMIN", email="admin@woodcommerce.local")
    create_user("ADMIN", email="no-telegram@woodcommerce.local")
    link_telegram(customer, 1001)
    link_telegram(admin, 2002)

    make_order(client, customer)

    assert sorted(sent) == [1001, 2002]


def test_logged_out_customer_gets_nothing(client, monkeypatch):
    sent = capture_messages(monkeypatch)
    customer = create_user(phone="+79991112233")
    admin = create_user("ADMIN", email="admin@woodcommerce.local")
    link_telegram(admin, 2002)

    make_order(client, customer)

    assert sent == [2002]


def test_admin_who_changed_status_is_not_notified(client, monkeypatch):
    customer = create_user(phone="+79991112233")
    actor = create_user("ADMIN", email="actor@woodcommerce.local")
    other = create_user("ADMIN", email="other@woodcommerce.local")
    link_telegram(customer, 1001)
    link_telegram(actor, 2002)
    link_telegram(other, 3003)
    order_id = make_order(client, customer)
    sent = capture_messages(monkeypatch)

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "CONFIRMED"},
        headers=headers(actor),
    )

    assert response.status_code == 200
    assert sorted(sent) == [1001, 3003]
