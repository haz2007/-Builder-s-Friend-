
from app.models import Category, Product, User
from app.auth import hash_password
from app.database import SessionLocal


def create_customer(
    db,
    email="customer@woodcommerce.local"
):
    customer = User(
        email=email,
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


def test_customer_cannot_order_inactive_product(client, reset_database):
    db = SessionLocal()

    create_customer(db)
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
        "customer@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "delivery_address": "Москва, ул. Ленина, 10",
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 2
                }
            ]
        }
    )

    assert response.status_code == 404
    assert response.json()["detail"] == f"Product {product.id} not found"

    db.refresh(product)

    assert product.stock_quantity == 20

    db.close()


def test_customer_can_order_product_and_stock_decreases(
    client,
    reset_database
):
    db = SessionLocal()

    create_customer(db)
    category = create_category(db)

    product = Product(
        name="Доска",
        description="Обычная доска",
        price=1000,
        stock_quantity=20,
        unit="шт",
        category_id=category.id,
        is_active=1
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    token = login(
        client,
        "customer@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "delivery_address": "Москва, ул. Ленина, 10",
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 5
                }
            ]
        }
    )

    assert response.status_code == 200

    db.refresh(product)

    assert product.stock_quantity == 15

    db.close()


def test_customer_cannot_order_more_than_stock(
    client,
    reset_database
):
    db = SessionLocal()

    create_customer(db)
    category = create_category(db)

    product = Product(
        name="Брус",
        description="Строительный брус",
        price=2000,
        stock_quantity=5,
        unit="шт",
        category_id=category.id,
        is_active=1
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    token = login(
        client,
        "customer@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "delivery_address": "Москва, ул. Ленина, 10",
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 6
                }
            ]
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"Not enough stock for product {product.id}"
    )

    db.refresh(product)

    assert product.stock_quantity == 5

    db.close()


def test_order_does_not_partially_change_stock(
    client,
    reset_database
):
    db = SessionLocal()

    create_customer(db)
    category = create_category(db)

    product_one = Product(
        name="Доска",
        description="Обычная доска",
        price=1000,
        stock_quantity=10,
        unit="шт",
        category_id=category.id,
        is_active=1
    )

    product_two = Product(
        name="Брус",
        description="Строительный брус",
        price=2000,
        stock_quantity=2,
        unit="шт",
        category_id=category.id,
        is_active=1
    )

    db.add(product_one)
    db.add(product_two)
    db.commit()

    db.refresh(product_one)
    db.refresh(product_two)

    token = login(
        client,
        "customer@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "delivery_address": "Москва, ул. Ленина, 10",
            "items": [
                {
                    "product_id": product_one.id,
                    "quantity": 3
                },
                {
                    "product_id": product_two.id,
                    "quantity": 5
                }
            ]
        }
    )

    assert response.status_code == 400

    db.refresh(product_one)
    db.refresh(product_two)

    assert product_one.stock_quantity == 10
    assert product_two.stock_quantity == 2

    db.close()


def test_customer_can_get_own_order(client, reset_database):
    db = SessionLocal()

    create_customer(db)
    category = create_category(db)

    product = Product(
        name="Доска",
        description="Обычная доска",
        price=1000,
        stock_quantity=20,
        unit="шт",
        category_id=category.id,
        is_active=1
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    token = login(
        client,
        "customer@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "delivery_address": "Москва, ул. Ленина, 10",
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 2
                }
            ]
        }
    )

    assert response.status_code == 200

    order_id = response.json()["id"]

    response = client.get(
        f"/api/v1/orders/{order_id}",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["id"] == order_id
    assert response.json()["delivery_address"] == "Москва, ул. Ленина, 10"
    assert response.json()["status"] == "NEW"

    db.close()


def test_customer_cannot_get_another_customer_order(
    client,
    reset_database
):
    db = SessionLocal()

    first_customer = create_customer(
        db,
        "customer1@woodcommerce.local"
    )

    second_customer = create_customer(
        db,
        "customer2@woodcommerce.local"
    )

    category = create_category(db)

    product = Product(
        name="Доска",
        description="Обычная доска",
        price=1000,
        stock_quantity=20,
        unit="шт",
        category_id=category.id,
        is_active=1
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    first_token = login(
        client,
        "customer1@woodcommerce.local",
        "123456"
    )

    response = client.post(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {first_token}"
        },
        json={
            "delivery_address": "Москва, ул. Ленина, 10",
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 2
                }
            ]
        }
    )

    assert response.status_code == 200

    order_id = response.json()["id"]

    second_token = login(
        client,
        "customer2@woodcommerce.local",
        "123456"
    )

    response = client.get(
        f"/api/v1/orders/{order_id}",
        headers={
            "Authorization": f"Bearer {second_token}"
        }
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You do not have access to this order"
    )

    db.close()
