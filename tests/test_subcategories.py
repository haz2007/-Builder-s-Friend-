from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import User


def admin_headers():
    db = SessionLocal()
    admin = User(
        email="admin_subcategories@woodcommerce.local",
        password_hash=hash_password("password123"),
        role="ADMIN",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.close()
    token = create_access_token(user_id=admin.id, role=admin.role)
    return {"Authorization": f"Bearer {token}"}


def create_category(client, headers, name, parent_id=None):
    return client.post(
        "/api/v1/categories/",
        json={"name": name, "parent_id": parent_id},
        headers=headers,
    )


def test_parent_category_lists_products_of_subcategories(client: TestClient):
    headers = admin_headers()
    lumber = create_category(client, headers, "Пиломатериалы").json()
    boards = create_category(client, headers, "Доска", lumber["id"]).json()

    product = client.post(
        "/api/v1/products/",
        json={
            "name": "Доска 50×150×6000",
            "price": 600,
            "stock_quantity": 10,
            "unit": "шт",
            "category_id": boards["id"],
        },
        headers=headers,
    ).json()

    by_parent = client.get(f"/api/v1/products/?category_id={lumber['id']}").json()
    by_child = client.get(f"/api/v1/products/?category_id={boards['id']}").json()

    assert boards["parent_id"] == lumber["id"]
    assert [p["id"] for p in by_parent] == [product["id"]]
    assert [p["id"] for p in by_child] == [product["id"]]


def test_only_two_levels_allowed(client: TestClient):
    headers = admin_headers()
    lumber = create_category(client, headers, "Пиломатериалы").json()
    boards = create_category(client, headers, "Доска", lumber["id"]).json()

    response = create_category(client, headers, "Доска половая", boards["id"])

    assert response.status_code == 400


def test_rename_keeps_parent(client: TestClient):
    headers = admin_headers()
    lumber = create_category(client, headers, "Пиломатериалы").json()
    boards = create_category(client, headers, "Доска", lumber["id"]).json()

    response = client.patch(
        f"/api/v1/categories/{boards['id']}",
        json={"name": "Доска обрезная"},
        headers=headers,
    )

    assert response.json()["parent_id"] == lumber["id"]


def test_cannot_delete_category_with_subcategories(client: TestClient):
    headers = admin_headers()
    lumber = create_category(client, headers, "Пиломатериалы").json()
    create_category(client, headers, "Доска", lumber["id"])

    response = client.delete(f"/api/v1/categories/{lumber['id']}", headers=headers)

    assert response.status_code == 409


def test_categories_follow_position_then_name(client: TestClient):
    headers = admin_headers()
    tools = create_category(client, headers, "Инструмент").json()
    lumber = create_category(client, headers, "Пиломатериалы").json()
    beams = create_category(client, headers, "Брус", lumber["id"]).json()
    boards = create_category(client, headers, "Доска", lumber["id"]).json()

    # Без позиции — по алфавиту
    names = [c["name"] for c in client.get("/api/v1/categories/").json()]
    assert names == ["Инструмент", "Пиломатериалы", "Брус", "Доска"]

    client.patch(f"/api/v1/categories/{lumber['id']}", json={"name": "Пиломатериалы", "position": 10},
                 headers=headers)
    client.patch(f"/api/v1/categories/{boards['id']}", json={"name": "Доска", "position": 10}, headers=headers)
    names = [c["name"] for c in client.get("/api/v1/categories/").json()]
    assert names == ["Пиломатериалы", "Инструмент", "Доска", "Брус"]

    # Переименование без позиции порядок не сбрасывает
    response = client.patch(f"/api/v1/categories/{lumber['id']}", json={"name": "Лес"}, headers=headers)
    assert response.json()["position"] == 10
    assert tools["position"] == 100 and beams["position"] == 100
