from app.models import Category, Product, User
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


def create_category(db):
    category = Category(name="Пиломатериалы")
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def login(client, email, password):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password
        }
    )
    return response.json()["access_token"]


def test_admin_can_create_product(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()

    create_admin(db)
    category = create_category(db)

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/products/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Доска 50x150",
            "description": "Строительная доска",
            "price": 1200,
            "stock_quantity": 100,
            "unit": "шт",
            "category_id": category.id
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Доска 50x150"
    assert data["price"] == 1200
    assert data["stock_quantity"] == 100

    db.close()


def test_customer_cannot_create_product(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()

    create_customer(db)
    category = create_category(db)

    token = login(
        client,
        "customer@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/products/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Доска",
            "description": "Доска",
            "price": 1000,
            "stock_quantity": 10,
            "unit": "шт",
            "category_id": category.id
        }
    )

    assert response.status_code == 403

    db.close()


def test_create_product_with_invalid_category(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()

    create_admin(db)

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/products/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Доска",
            "description": "Доска",
            "price": 1000,
            "stock_quantity": 10,
            "unit": "шт",
            "category_id": 999
        }
    )

    assert response.status_code == 404

    db.close()


def test_admin_can_update_product(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()

    create_admin(db)
    category = create_category(db)

    product = Product(
        name="Старая доска",
        description="Старая",
        price=1000,
        stock_quantity=20,
        unit="шт",
        category_id=category.id
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.patch(
        f"/api/v1/products/{product.id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Новая доска",
            "description": "Обновлённая доска",
            "price": 1500,
            "stock_quantity": 50,
            "unit": "шт",
            "category_id": category.id
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Новая доска"
    assert data["price"] == 1500
    assert data["stock_quantity"] == 50

    db.close()


def test_admin_can_delete_product(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()

    create_admin(db)
    category = create_category(db)

    product = Product(
        name="Доска",
        description="Доска",
        price=1000,
        stock_quantity=20,
        unit="шт",
        category_id=category.id
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.delete(
        f"/api/v1/products/{product.id}",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    db.close()


def test_admin_can_partially_update_product(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()

    create_admin(db)
    category = create_category(db)

    product = Product(
        name="Доска",
        description="Обычная доска",
        price=1000,
        stock_quantity=20,
        unit="шт",
        category_id=category.id
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.patch(
        f"/api/v1/products/{product.id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "price": 1500
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Доска"
    assert data["description"] == "Обычная доска"
    assert data["price"] == 1500
    assert data["stock_quantity"] == 20
    assert data["unit"] == "шт"

    db.close()


    def test_admin_soft_deletes_product(client, reset_database):
        from app.database import SessionLocal

        db = SessionLocal()

        create_admin(db)
        category = create_category(db)

        product = Product(
            name="Доска",
            description="Обычная доска",
            price=1000,
            stock_quantity=20,
            unit="шт",
            category_id=category.id
        )

        db.add(product)
        db.commit()
        db.refresh(product)

        token = login(
            client,
            "admin@woodcommerce.local",
            "123456"
        )

        response = client.delete(
            f"/api/v1/products/{product.id}",
            headers={
                "Authorization": f"Bearer {token}"
            }
        )

        assert response.status_code == 200

        db.refresh(product)

        assert product.is_active == 0

        response = client.get(
            f"/api/v1/products/{product.id}"
        )

        assert response.status_code == 404

        db.close()


def test_admin_can_restore_product(client, reset_database):
    from app.database import SessionLocal

    db = SessionLocal()

    create_admin(db)
    category = create_category(db)

    product = Product(
        name="Доска",
        description="Обычная доска",
        price=1000,
        stock_quantity=20,
        unit="шт",
        category_id=category.id,
        is_active=0
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    token = login(
        client,
        "admin@woodcommerce.local",
        "123456"
    )

    response = client.post(
        f"/api/v1/products/{product.id}/restore",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    db.refresh(product)

    assert product.is_active == 1

    response = client.get(
        f"/api/v1/products/{product.id}"
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Доска"

    db.close()