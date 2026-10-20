from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Order, OrderItem, Product, User


def create_customer(email):
    db = SessionLocal()

    customer = User(
        email=email,
        password_hash=hash_password("password123"),
        role="CUSTOMER"
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)
    db.close()

    return customer


def create_product(stock_quantity=10):
    db = SessionLocal()

    category = Category(
        name="Test Category"
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    product = Product(
        name="Test Product",
        description="Test description",
        price=100,
        stock_quantity=stock_quantity,
        unit="шт",
        category_id=category.id
    )

    db.add(product)
    db.commit()
    db.refresh(product)
    db.close()

    return product


def create_order(customer_id, product_id, quantity=3, status="NEW"):
    db = SessionLocal()

    order = Order(
        customer_name="Тестовый покупатель",
        user_id=customer_id,
        status=status,
        total_price=300,
        delivery_address="Москва, улица Ленина, 1"
    )

    db.add(order)
    db.flush()

    product = db.get(Product, product_id)

    order_item = OrderItem(
        order_id=order.id,
        product_id=product_id,
        variant_id=product.variants[0].id,
        quantity=quantity,
        price=100,
        unit=product.unit,
    )

    db.add(order_item)
    db.commit()
    db.refresh(order)
    db.close()

    return order


def get_token(user):
    return create_access_token(
        user_id=user.id,
        role=user.role
    )


def test_customer_can_cancel_new_order(client: TestClient):
    customer = create_customer(
        "cancel_order_customer@woodcommerce.local"
    )
    product = create_product(stock_quantity=7)

    order = create_order(
        customer.id,
        product.id,
        quantity=3
    )

    token = get_token(customer)

    response = client.post(
        f"/api/v1/orders/{order.id}/cancel",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    cancelled_order = response.json()

    assert cancelled_order["status"] == "CANCELLED"

    db = SessionLocal()
    updated_product = db.query(Product).filter(
        Product.id == product.id
    ).first()

    assert updated_product.stock_quantity == 10

    db.close()


def test_customer_cannot_cancel_other_customer_order(client: TestClient):
    customer = create_customer(
        "cancel_order_customer_2@woodcommerce.local"
    )
    other_customer = create_customer(
        "cancel_order_other@woodcommerce.local"
    )

    product = create_product(stock_quantity=10)

    order = create_order(
        other_customer.id,
        product.id
    )

    token = get_token(customer)

    response = client.post(
        f"/api/v1/orders/{order.id}/cancel",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 403


def test_customer_cannot_cancel_non_new_order(client: TestClient):
    customer = create_customer(
        "cancel_order_customer_3@woodcommerce.local"
    )

    product = create_product(stock_quantity=10)

    order = create_order(
        customer.id,
        product.id,
        status="CONFIRMED"
    )

    token = get_token(customer)

    response = client.post(
        f"/api/v1/orders/{order.id}/cancel",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 400


def test_cancel_nonexistent_order(client: TestClient):
    customer = create_customer(
        "cancel_order_customer_4@woodcommerce.local"
    )

    token = get_token(customer)

    response = client.post(
        "/api/v1/orders/99999/cancel",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 404
