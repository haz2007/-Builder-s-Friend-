from app.database import SessionLocal
from app.models import Category, Product


def create_product(name="Notification Test Product"):
    db = SessionLocal()

    category = Category(
        name=f"{name} Category"
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    product = Product(
        name=name,
        description="Product for notification tests",
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
    # Generate a valid, deterministic phone number unique to the test email.
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


def create_order(client, token, product):
    response = client.post(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "customer_name": "Тестовый покупатель",
            "delivery_address": "Notification Street 1",
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1
                }
            ]
        }
    )

    assert response.status_code == 200

    return response.json()["id"]


def test_notification_created_when_order_is_cancelled(client):
    token = register_and_login(
        client,
        "notification_customer@example.com"
    )

    product = create_product()
    order_id = create_order(client, token, product)

    cancel_response = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert cancel_response.status_code == 200

    notifications_response = client.get(
        "/api/v1/notifications/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert notifications_response.status_code == 200

    notifications = notifications_response.json()

    assert len(notifications) == 1
    assert notifications[0]["order_id"] == order_id
    assert notifications[0]["status"] == "CANCELLED"
    assert notifications[0]["message"] == "Ваш заказ отменён."
    assert notifications[0]["is_read"] == 0


def test_customer_cannot_see_another_customer_notifications(client):
    owner_token = register_and_login(
        client,
        "notification_owner@example.com"
    )

    product = create_product()
    order_id = create_order(client, owner_token, product)

    cancel_response = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={
            "Authorization": f"Bearer {owner_token}"
        }
    )

    assert cancel_response.status_code == 200

    other_token = register_and_login(
        client,
        "notification_other@example.com"
    )

    notifications_response = client.get(
        "/api/v1/notifications/",
        headers={
            "Authorization": f"Bearer {other_token}"
        }
    )

    assert notifications_response.status_code == 200
    assert notifications_response.json() == []


def test_customer_can_mark_notification_as_read(client):
    token = register_and_login(
        client,
        "notification_read@example.com"
    )

    product = create_product()
    order_id = create_order(client, token, product)

    cancel_response = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert cancel_response.status_code == 200

    notifications = client.get(
        "/api/v1/notifications/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    ).json()

    assert len(notifications) == 1

    notification_id = notifications[0]["id"]

    read_response = client.patch(
        f"/api/v1/notifications/{notification_id}/read",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert read_response.status_code == 200
    assert read_response.json()["is_read"] == 1


def test_customer_can_mark_all_notifications_as_read(client):
    token = register_and_login(
        client,
        "notification_read_all@example.com"
    )

    product1 = create_product("Notification Product 1")
    product2 = create_product("Notification Product 2")

    order_id_1 = create_order(
        client,
        token,
        product1
    )

    order_id_2 = create_order(
        client,
        token,
        product2
    )

    for order_id in [order_id_1, order_id_2]:
        cancel_response = client.post(
            f"/api/v1/orders/{order_id}/cancel",
            headers={
                "Authorization": f"Bearer {token}"
            }
        )

        assert cancel_response.status_code == 200

    notifications = client.get(
        "/api/v1/notifications/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    ).json()

    assert len(notifications) == 2

    read_all_response = client.patch(
        "/api/v1/notifications/read-all",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert read_all_response.status_code == 200
    assert read_all_response.json()["count"] == 2

    notifications = client.get(
        "/api/v1/notifications/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    ).json()

    assert len(notifications) == 2

    for notification in notifications:
        assert notification["is_read"] == 1

def test_customer_can_get_unread_notifications_count(client):
    token = register_and_login(
        client,
        "notification_count@example.com"
    )

    product = create_product()
    order_id = create_order(client, token, product)

    cancel_response = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert cancel_response.status_code == 200

    count_response = client.get(
        "/api/v1/notifications/unread-count",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert count_response.status_code == 200
    assert count_response.json()["count"] == 1


def test_customer_can_get_only_unread_notifications(client):
    token = register_and_login(
        client,
        "notification_filter@example.com"
    )

    product = create_product()
    order_id = create_order(client, token, product)

    cancel_response = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert cancel_response.status_code == 200

    notifications = client.get(
        "/api/v1/notifications/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    ).json()

    assert len(notifications) == 1

    notification_id = notifications[0]["id"]

    read_response = client.patch(
        f"/api/v1/notifications/{notification_id}/read",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert read_response.status_code == 200

    unread_response = client.get(
        "/api/v1/notifications/?unread_only=true",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert unread_response.status_code == 200
    assert unread_response.json() == []


def test_customer_can_paginate_notifications(client):
    token = register_and_login(
        client,
        "notification_pagination@example.com"
    )

    product1 = create_product("Pagination Product 1")
    product2 = create_product("Pagination Product 2")

    for product in [product1, product2]:
        order_id = create_order(
            client,
            token,
            product
        )

        cancel_response = client.post(
            f"/api/v1/orders/{order_id}/cancel",
            headers={
                "Authorization": f"Bearer {token}"
            }
        )

        assert cancel_response.status_code == 200

    first_page = client.get(
        "/api/v1/notifications/?limit=1&offset=0",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert first_page.status_code == 200
    assert len(first_page.json()) == 1

    second_page = client.get(
        "/api/v1/notifications/?limit=1&offset=1",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert second_page.status_code == 200
    assert len(second_page.json()) == 1

    assert (
        first_page.json()[0]["id"]
        != second_page.json()[0]["id"]
    )
