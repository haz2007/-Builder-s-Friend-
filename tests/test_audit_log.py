"""Журнал действий в админке: товары, варианты, категории, админы, пароли."""

from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import User


def make_user(role, phone, **fields):
    db = SessionLocal()
    user = User(phone=phone, password_hash=hash_password("x"), role=role, **fields)
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()
    return user_id


def auth(user_id, role):
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id, role=role)}"}


def audit(client, headers):
    return client.get("/api/v1/admin/audit", headers=headers).json()


def setup(client):
    admin_id = make_user("ADMIN", "+79990000001", email="admin@woodcommerce.local", is_owner=1)
    headers = auth(admin_id, "ADMIN")
    category = client.post("/api/v1/categories/", json={"name": "Доска"}, headers=headers).json()
    product = client.post(
        "/api/v1/products/",
        json={"name": "Доска 50×150", "price": 600, "stock_quantity": 100, "unit": "шт",
              "category_id": category["id"]},
        headers=headers,
    ).json()
    return headers, category, product


def test_price_and_stock_change_is_logged_with_before_after(client: TestClient):
    headers, _, product = setup(client)

    client.patch(f"/api/v1/products/{product['id']}", json={"price": 650, "stock_quantity": 120}, headers=headers)

    entry = audit(client, headers)[0]
    assert entry["action"] == "product.updated"
    assert entry["actor"] == "admin@woodcommerce.local"
    assert "цена 600 → 650" in entry["summary"]
    assert "остаток 100 → 120" in entry["summary"]
    assert entry["changes"]["price"] == [600, 650]


def test_saving_without_changes_is_not_logged(client: TestClient):
    headers, _, product = setup(client)
    before = len(audit(client, headers))

    client.patch(f"/api/v1/products/{product['id']}", json={"price": 600}, headers=headers)

    assert len(audit(client, headers)) == before


def test_hide_restore_and_variants_are_logged(client: TestClient):
    headers, _, product = setup(client)
    client.delete(f"/api/v1/products/{product['id']}", headers=headers)
    client.post(f"/api/v1/products/{product['id']}/restore", headers=headers)
    variant = client.post(
        f"/api/v1/products/{product['id']}/variants",
        json={"name": "Пачка 10 шт", "unit": "пачка", "price": 5800, "base_quantity": 10},
        headers=headers,
    ).json()
    client.patch(f"/api/v1/products/{product['id']}/variants/{variant['id']}", json={"price": 5500},
                 headers=headers)

    actions = [entry["action"] for entry in audit(client, headers)]
    assert actions[:4] == ["variant.updated", "variant.created", "product.restored", "product.hidden"]
    assert "product.created" in actions and "category.created" in actions


def test_admin_management_and_password_reset_are_logged(client: TestClient):
    headers, _, _ = setup(client)
    customer_id = make_user("CUSTOMER", "+79991234567")

    client.post("/api/v1/admins/", json={"login": "+79991234567"}, headers=headers)
    client.delete(f"/api/v1/admins/{customer_id}", headers=headers)
    response = client.post(f"/api/v1/users/{customer_id}/reset-password", headers=headers)

    entries = audit(client, headers)
    assert [entry["action"] for entry in entries][:3] == ["password.reset", "admin.removed", "admin.added"]
    # Временный пароль в журнал не попадает
    assert response.json()["temporary_password"] not in entries[0]["summary"]


def test_audit_log_for_admins_only(client: TestClient):
    customer_id = make_user("CUSTOMER", "+79991234568")

    assert client.get("/api/v1/admin/audit", headers=auth(customer_id, "CUSTOMER")).status_code == 403
