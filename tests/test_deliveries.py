from app.auth import hash_password
from app.models import User, Product, Category
from app.database import SessionLocal


def create_user(email, role):
    db = SessionLocal()

    user = User(
        email=email,
        password_hash=hash_password("123456"),
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    db.close()

    return user


def create_product():
    db = SessionLocal()

    category = Category(name="Пиломатериалы")
    db.add(category)
    db.commit()
    db.refresh(category)

    product = Product(
        name="Доска",
        description="Обычная доска",
        price=100,
        stock_quantity=100,
        unit="шт",
        category_id=category.id,
        is_active=1
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    db.close()

    return product


def get_token(client, email):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "123456"
        }
    )

    assert response.status_code == 200

    return response.json()["access_token"]


def test_admin_can_create_delivery(client):
    admin = create_user(
        "admin@woodcommerce.local",
        "ADMIN"
    )

    customer = create_user(
        "customer@woodcommerce.local",
        "CUSTOMER"
    )

    product = create_product()

    customer_token = get_token(
        client,
        customer.email
    )

    order_response = client.post(
        "/api/v1/orders/",
        json={
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 2
                }
            ],
            "delivery_address": "Москва, ул. Ленина, 10"
        },
        headers={
            "Authorization": f"Bearer {customer_token}"
        }
    )

    assert order_response.status_code == 200

    order_id = order_response.json()["id"]

    admin_token = get_token(
        client,
        admin.email
    )

    status_response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={
            "status": "CONFIRMED"
        },
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    assert status_response.status_code == 200

    status_response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={
            "status": "PREPARING"
        },
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    assert status_response.status_code == 200

    status_response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={
            "status": "READY_FOR_DELIVERY"
        },
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    assert status_response.status_code == 200

    delivery_response = client.post(
        f"/api/v1/deliveries/{order_id}",
        json={
            "address": "Москва, ул. Ленина, 10"
        },
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    assert delivery_response.status_code == 200

    delivery = delivery_response.json()

    assert delivery["status"] == "WAITING"
    assert delivery["order_id"] == order_id
    assert delivery["address"] == "Москва, ул. Ленина, 10"


def test_admin_can_assign_driver(client):
    admin = create_user(
        "admin@woodcommerce.local",
        "ADMIN"
    )

    driver = create_user(
        "driver@woodcommerce.local",
        "DRIVER"
    )

    customer = create_user(
        "customer@woodcommerce.local",
        "CUSTOMER"
    )

    product = create_product()

    customer_token = get_token(
        client,
        customer.email
    )

    order_response = client.post(
        "/api/v1/orders/",
        json={
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1
                }
            ],
            "delivery_address": "Москва, ул. Пушкина, 15"
        },
        headers={
            "Authorization": f"Bearer {customer_token}"
        }
    )

    order_id = order_response.json()["id"]

    admin_token = get_token(
        client,
        admin.email
    )

    for status in [
        "CONFIRMED",
        "PREPARING",
        "READY_FOR_DELIVERY"
    ]:
        response = client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={
                "status": status
            },
            headers={
                "Authorization": f"Bearer {admin_token}"
            }
        )

        assert response.status_code == 200

    delivery_response = client.post(
        f"/api/v1/deliveries/{order_id}",
        json={
            "address": "Москва, ул. Пушкина, 15"
        },
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    assert delivery_response.status_code == 200

    delivery_id = delivery_response.json()["id"]

    assign_response = client.patch(
        f"/api/v1/deliveries/{delivery_id}/assign/{driver.id}",
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    assert assign_response.status_code == 200

    delivery = assign_response.json()

    assert delivery["driver_id"] == driver.id
    assert delivery["status"] == "WAITING"

    order_response = client.get(
        f"/api/v1/orders/{order_id}",
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    assert order_response.status_code == 200
    assert order_response.json()["status"] == "ASSIGNED_TO_DRIVER"


def test_driver_can_update_delivery_status(client):
    admin = create_user(
        "admin@woodcommerce.local",
        "ADMIN"
    )

    driver = create_user(
        "driver@woodcommerce.local",
        "DRIVER"
    )

    customer = create_user(
        "customer@woodcommerce.local",
        "CUSTOMER"
    )

    product = create_product()

    customer_token = get_token(
        client,
        customer.email
    )

    order_response = client.post(
        "/api/v1/orders/",
        json={
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1
                }
            ],
            "delivery_address": "Москва, ул. Гагарина, 20"
        },
        headers={
            "Authorization": f"Bearer {customer_token}"
        }
    )

    order_id = order_response.json()["id"]

    admin_token = get_token(
        client,
        admin.email
    )

    for status in [
        "CONFIRMED",
        "PREPARING",
        "READY_FOR_DELIVERY"
    ]:
        response = client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={
                "status": status
            },
            headers={
                "Authorization": f"Bearer {admin_token}"
            }
        )

        assert response.status_code == 200

    delivery_response = client.post(
        f"/api/v1/deliveries/{order_id}",
        json={
            "address": "Москва, ул. Гагарина, 20"
        },
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    delivery_id = delivery_response.json()["id"]

    assign_response = client.patch(
        f"/api/v1/deliveries/{delivery_id}/assign/{driver.id}",
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    assert assign_response.status_code == 200

    driver_token = get_token(
        client,
        driver.email
    )

    response = client.patch(
        f"/api/v1/deliveries/{delivery_id}/status",
        json={
            "status": "LOADED"
        },
        headers={
            "Authorization": f"Bearer {driver_token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["status"] == "LOADED"

    response = client.patch(
        f"/api/v1/deliveries/{delivery_id}/status",
        json={
            "status": "ON_THE_WAY"
        },
        headers={
            "Authorization": f"Bearer {driver_token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ON_THE_WAY"

    order_response = client.get(
        f"/api/v1/orders/{order_id}",
        headers={
            "Authorization": f"Bearer {driver_token}"
        }
    )

    assert order_response.status_code == 403

    response = client.patch(
        f"/api/v1/deliveries/{delivery_id}/status",
        json={
            "status": "DELIVERED"
        },
        headers={
            "Authorization": f"Bearer {driver_token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["status"] == "DELIVERED"


def test_customer_cannot_manage_delivery(client):
    admin = create_user(
        "admin@woodcommerce.local",
        "ADMIN"
    )

    customer = create_user(
        "customer@woodcommerce.local",
        "CUSTOMER"
    )

    product = create_product()

    customer_token = get_token(
        client,
        customer.email
    )

    order_response = client.post(
        "/api/v1/orders/",
        json={
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 1
                }
            ],
            "delivery_address": "Москва, ул. Мира, 5"
        },
        headers={
            "Authorization": f"Bearer {customer_token}"
        }
    )

    order_id = order_response.json()["id"]

    admin_token = get_token(
        client,
        admin.email
    )

    for status in [
        "CONFIRMED",
        "PREPARING",
        "READY_FOR_DELIVERY"
    ]:
        response = client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={
                "status": status
            },
            headers={
                "Authorization": f"Bearer {admin_token}"
            }
        )

        assert response.status_code == 200

    delivery_response = client.post(
        f"/api/v1/deliveries/{order_id}",
        json={
            "address": "Москва, ул. Мира, 5"
        },
        headers={
            "Authorization": f"Bearer {admin_token}"
        }
    )

    assert delivery_response.status_code == 200

    delivery_id = delivery_response.json()["id"]

    response = client.get(
        f"/api/v1/deliveries/{delivery_id}",
        headers={
            "Authorization": f"Bearer {customer_token}"
        }
    )

    assert response.status_code == 403