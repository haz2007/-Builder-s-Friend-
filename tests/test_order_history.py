from app.database import SessionLocal
from app.models import Category, Product


def create_product():
    db = SessionLocal()

    category = Category(
        name="History Test Category"
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    product = Product(
        name="History Test Product",
        description="Product for order history tests",
        price=100,
        stock_quantity=10,
        unit="pcs",
        category_id=category.id,
        is_active=1
    )

    db.add(product)
    db.commit()
    db.refresh(product)
    db.close()

    return product


def register_and_login(client, email):
    # Use a valid, deterministic, email-specific phone number.
    import hashlib
    phone = "+7999" + str(
        int(hashlib.sha256(email.encode("utf-8")).hexdigest(), 16) % 10_000_000
    ).zfill(7)
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "phone": phone,
            "password": "password123", "privacy_accepted": True
        }
    )

    assert register_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "phone": phone,
            "password": "password123"
        }
    )

    assert login_response.status_code == 200

    return login_response.json()["access_token"]


def test_customer_can_get_own_order_history(client):
    token = register_and_login(
        client,
        "history_customer@example.com"
    )

    product = create_product()

    order_response = client.post(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "customer_name": "Тестовый покупатель",
            "delivery_address": "History Street 1",
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1
                }
            ]
        }
    )

    assert order_response.status_code == 200

    order_id = order_response.json()["id"]

    history_response = client.get(
        f"/api/v1/orders/{order_id}/history",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 1
    assert history[0]["order_id"] == order_id
    assert history[0]["status"] == "NEW"


def test_customer_cannot_get_another_customer_order_history(client):
    token = register_and_login(
        client,
        "history_customer@example.com"
    )

    product = create_product()

    order_response = client.post(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "customer_name": "Тестовый покупатель",
            "delivery_address": "History Street 1",
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1
                }
            ]
        }
    )

    assert order_response.status_code == 200

    order_id = order_response.json()["id"]

    other_token = register_and_login(
        client,
        "other_history_customer@example.com"
    )

    history_response = client.get(
        f"/api/v1/orders/{order_id}/history",
        headers={
            "Authorization": f"Bearer {other_token}"
        }
    )

    assert history_response.status_code == 403
