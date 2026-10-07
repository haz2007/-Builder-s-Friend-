from app.models import Category, User
from app.auth import hash_password


def create_admin(db):
    admin = User(
        email="admin@woodcommerce.local",
        password_hash=hash_password("123456"),
        role="ADMIN"
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def create_customer(db):
    customer = User(
        email="customer@woodcommerce.local",
        password_hash=hash_password("123456"),
        role="CUSTOMER"
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def login(client, email, password):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password
        }
    )
    return response.json()["access_token"]


def test_admin_can_create_category(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()
    create_admin(db)

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/categories/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Пиломатериалы"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Пиломатериалы"
    assert "id" in data

    db.close()


def test_customer_cannot_create_category(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()
    create_customer(db)

    token = login(
        client,
        "customer@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/categories/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Пиломатериалы"
        }
    )

    assert response.status_code == 403

    db.close()


def test_admin_can_get_category(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()
    create_admin(db)

    category = Category(name="Доска")
    db.add(category)
    db.commit()
    db.refresh(category)

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.get(
        f"/api/v1/categories/{category.id}",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Доска"

    db.close()


def test_admin_can_update_category(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()
    create_admin(db)

    category = Category(name="Старая категория")
    db.add(category)
    db.commit()
    db.refresh(category)

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.patch(
        f"/api/v1/categories/{category.id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Новая категория"
        }
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Новая категория"

    db.close()


def test_cannot_create_duplicate_category(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()
    create_admin(db)

    category = Category(name="Пиломатериалы")
    db.add(category)
    db.commit()

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/categories/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Пиломатериалы"
        }
    )

    assert response.status_code == 400

    db.close()