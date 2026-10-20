from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, ProductVariant, User, pieces_in_cubic_meter


def create_user(email, role):
    db = SessionLocal()

    user = User(
        email=email,
        password_hash=hash_password("password123"),
        role=role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    return user


def auth_headers(user):
    token = create_access_token(user_id=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def create_category(name="Пиломатериалы"):
    db = SessionLocal()

    category = Category(name=name)

    db.add(category)
    db.commit()
    db.refresh(category)
    db.close()

    return category


def setup_board(client: TestClient, stock_pieces=300):
    """Доска 50x150x6000: склад в штуках, продаётся поштучно и кубами.

    Объём доски 0,045 м³ → 22,22 шт в кубе → 22 шт.
    """
    admin = create_user("admin_variants@woodcommerce.local", "ADMIN")
    category = create_category()

    product = client.post(
        "/api/v1/products/",
        json={
            "name": "Доска обрезная 50x150x6000",
            "price": 700,
            "stock_quantity": stock_pieces,
            "unit": "шт",
            "category_id": category.id,
            "thickness_mm": 50,
            "width_mm": 150,
            "length_mm": 6000,
        },
        headers=auth_headers(admin),
    ).json()

    cube = client.post(
        f"/api/v1/products/{product['id']}/variants",
        json={"name": "Куб", "unit": "м3", "price": 15000},
        headers=auth_headers(admin),
    ).json()

    piece = product["variants"][0]

    return admin, product, piece, cube


def get_product(product_id):
    db = SessionLocal()
    product = db.get(Product, product_id)
    db.close()
    return product


def get_variant(variant_id):
    db = SessionLocal()
    variant = db.get(ProductVariant, variant_id)
    db.close()
    return variant


def create_order(client, customer, items):
    return client.post(
        "/api/v1/orders/",
        json={
            "customer_name": "Тестовый покупатель",
            "items": items,
            "delivery_address": "Москва, улица Ленина, 1",
        },
        headers=auth_headers(customer),
    )


def test_pieces_in_cubic_meter_rounds_down():
    # 1 / (0.05 * 0.15 * 6) = 22.22…
    assert pieces_in_cubic_meter(50, 150, 6000) == 22
    # 27,333 доски в кубе → 27 шт
    assert pieces_in_cubic_meter(40, 150, 6100) == 27
    # Ровно 20 шт не должно превратиться в 19 из-за погрешности
    assert pieces_in_cubic_meter(50, 200, 5000) == 20
    assert pieces_in_cubic_meter(None, 150, 6000) is None


def test_cube_variant_gets_pieces_per_cubic_meter(client: TestClient):
    _, product, piece, cube = setup_board(client)

    response = client.get(f"/api/v1/products/{product['id']}")

    data = response.json()
    assert data["pieces_per_cubic_meter"] == 22
    variants = {v["id"]: v for v in data["variants"]}
    assert variants[piece["id"]]["base_quantity"] == 1
    assert variants[piece["id"]]["stock_quantity"] == 300
    assert variants[cube["id"]]["base_quantity"] == 22
    # 300 шт / 22 = 13,6 → 13 целых кубов
    assert variants[cube["id"]]["stock_quantity"] == 13


def test_ordering_cubes_deducts_pieces(client: TestClient):
    _, product, _, cube = setup_board(client)
    customer = create_user("customer_cubes@woodcommerce.local", "CUSTOMER")

    response = create_order(
        client,
        customer,
        [{"product_id": product["id"], "variant_id": cube["id"], "quantity": 4}],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_price"] == 4 * 15000
    item = data["items"][0]
    assert item["unit"] == "м3"
    assert item["base_quantity"] == 22
    # 4 куба × 22 шт = 88 шт
    assert get_product(product["id"]).stock_quantity == 300 - 88


def test_pieces_and_cubes_share_stock(client: TestClient):
    _, product, piece, cube = setup_board(client, stock_pieces=50)
    customer = create_user("customer_shared@woodcommerce.local", "CUSTOMER")

    # 2 куба = 44 шт + 7 шт = 51 шт > 50 на складе
    response = create_order(
        client,
        customer,
        [
            {"product_id": product["id"], "variant_id": cube["id"], "quantity": 2},
            {"product_id": product["id"], "variant_id": piece["id"], "quantity": 7},
        ],
    )

    assert response.status_code == 400
    assert get_product(product["id"]).stock_quantity == 50

    response = create_order(
        client,
        customer,
        [
            {"product_id": product["id"], "variant_id": cube["id"], "quantity": 2},
            {"product_id": product["id"], "variant_id": piece["id"], "quantity": 6},
        ],
    )

    assert response.status_code == 200
    assert response.json()["total_price"] == 2 * 15000 + 6 * 700
    assert get_product(product["id"]).stock_quantity == 0


def test_fractional_cubes_are_rejected(client: TestClient):
    _, product, _, cube = setup_board(client)
    customer = create_user("customer_fraction@woodcommerce.local", "CUSTOMER")

    response = create_order(
        client,
        customer,
        [{"product_id": product["id"], "variant_id": cube["id"], "quantity": 1.5}],
    )

    assert response.status_code == 400
    assert get_product(product["id"]).stock_quantity == 300


def test_fasteners_allow_fractional_kilograms(client: TestClient):
    admin = create_user("admin_kg@woodcommerce.local", "ADMIN")
    category = create_category("Крепёж")
    product = client.post(
        "/api/v1/products/",
        json={
            "name": "Саморез 3.5x51",
            "price": 1000,
            "stock_quantity": 10,
            "unit": "кг",
            "category_id": category.id,
        },
        headers=auth_headers(admin),
    ).json()
    customer = create_user("customer_kg@woodcommerce.local", "CUSTOMER")

    response = create_order(
        client,
        customer,
        [{"product_id": product["id"], "quantity": 2.5}],
    )

    assert response.status_code == 200
    assert get_product(product["id"]).stock_quantity == 7.5


def test_order_without_variant_uses_primary(client: TestClient):
    _, product, _, _ = setup_board(client)
    customer = create_user("customer_primary@woodcommerce.local", "CUSTOMER")

    response = create_order(
        client,
        customer,
        [{"product_id": product["id"], "quantity": 3}],
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["unit"] == "шт"
    assert get_product(product["id"]).stock_quantity == 297


def test_variant_of_other_product_is_rejected(client: TestClient):
    admin, product, _, _ = setup_board(client)
    other_category = create_category("Крепёж")
    other = client.post(
        "/api/v1/products/",
        json={
            "name": "Саморез 3.5x51",
            "price": 1000,
            "stock_quantity": 50,
            "unit": "кг",
            "category_id": other_category.id,
        },
        headers=auth_headers(admin),
    ).json()
    customer = create_user("customer_other@woodcommerce.local", "CUSTOMER")

    response = create_order(
        client,
        customer,
        [{
            "product_id": product["id"],
            "variant_id": other["variants"][0]["id"],
            "quantity": 1,
        }],
    )

    assert response.status_code == 404


def test_cancel_returns_pieces_to_stock(client: TestClient):
    _, product, _, cube = setup_board(client)
    customer = create_user("customer_cancel@woodcommerce.local", "CUSTOMER")

    order = create_order(
        client,
        customer,
        [{"product_id": product["id"], "variant_id": cube["id"], "quantity": 2}],
    ).json()

    response = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert get_product(product["id"]).stock_quantity == 300


def test_cancel_uses_snapshot_after_dimensions_change(client: TestClient):
    admin, product, _, cube = setup_board(client)
    customer = create_user("customer_snapshot@woodcommerce.local", "CUSTOMER")

    order = create_order(
        client,
        customer,
        [{"product_id": product["id"], "variant_id": cube["id"], "quantity": 1}],
    ).json()

    # Поменяли длину: теперь в кубе другое число досок
    client.patch(
        f"/api/v1/products/{product['id']}",
        json={"length_mm": 3000},
        headers=auth_headers(admin),
    )
    assert get_variant(cube["id"]).base_quantity == 44

    client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        headers=auth_headers(customer),
    )

    # Вернулись те же 22 шт, что и были списаны
    assert get_product(product["id"]).stock_quantity == 300


def test_dimensions_require_piece_unit(client: TestClient):
    admin = create_user("admin_dims@woodcommerce.local", "ADMIN")
    category = create_category()

    response = client.post(
        "/api/v1/products/",
        json={
            "name": "Брус 100x100x6000",
            "price": 16000,
            "stock_quantity": 5,
            "unit": "м3",
            "category_id": category.id,
            "thickness_mm": 100,
            "width_mm": 100,
            "length_mm": 6000,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 400


def test_partial_dimensions_are_rejected(client: TestClient):
    admin = create_user("admin_partial@woodcommerce.local", "ADMIN")
    category = create_category()

    response = client.post(
        "/api/v1/products/",
        json={
            "name": "Брус",
            "price": 500,
            "stock_quantity": 5,
            "unit": "шт",
            "category_id": category.id,
            "thickness_mm": 100,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 400


def test_cannot_remove_last_active_variant(client: TestClient):
    admin = create_user("admin_last@woodcommerce.local", "ADMIN")
    category = create_category()
    product = client.post(
        "/api/v1/products/",
        json={
            "name": "Брус 100x100",
            "price": 16000,
            "stock_quantity": 5,
            "unit": "м3",
            "category_id": category.id,
        },
        headers=auth_headers(admin),
    ).json()
    variant_id = product["variants"][0]["id"]

    delete_response = client.delete(
        f"/api/v1/products/{product['id']}/variants/{variant_id}",
        headers=auth_headers(admin),
    )
    deactivate_response = client.patch(
        f"/api/v1/products/{product['id']}/variants/{variant_id}",
        json={"is_active": 0},
        headers=auth_headers(admin),
    )

    assert delete_response.status_code == 400
    assert deactivate_response.status_code == 400


def test_variant_used_in_orders_is_deactivated_not_deleted(client: TestClient):
    admin, product, _, cube = setup_board(client)
    customer = create_user("customer_used@woodcommerce.local", "CUSTOMER")
    create_order(
        client,
        customer,
        [{"product_id": product["id"], "variant_id": cube["id"], "quantity": 1}],
    )

    response = client.delete(
        f"/api/v1/products/{product['id']}/variants/{cube['id']}",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert get_variant(cube["id"]).is_active == 0


def test_updating_product_price_updates_primary_variant(client: TestClient):
    admin, product, piece, cube = setup_board(client)

    response = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"price": 750, "stock_quantity": 120},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()
    variants = {v["id"]: v for v in data["variants"]}
    assert data["stock_quantity"] == 120
    assert variants[piece["id"]]["price"] == 750
    assert variants[cube["id"]]["price"] == 15000
    assert variants[cube["id"]]["stock_quantity"] == 5


def test_customer_cannot_manage_variants(client: TestClient):
    _, product, _, _ = setup_board(client)
    customer = create_user("customer_manage@woodcommerce.local", "CUSTOMER")

    response = client.post(
        f"/api/v1/products/{product['id']}/variants",
        json={"name": "Штука", "unit": "шт", "price": 1},
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_filter_by_extra_category(client: TestClient):
    admin = create_user("admin_categories@woodcommerce.local", "ADMIN")
    lumber = create_category("Пиломатериалы")
    roofing = create_category("Кровля")

    product = client.post(
        "/api/v1/products/",
        json={
            "name": "Брусок 50x50",
            "price": 14000,
            "stock_quantity": 3,
            "unit": "м3",
            "category_id": lumber.id,
            "category_ids": [roofing.id],
        },
        headers=auth_headers(admin),
    ).json()

    response = client.get(f"/api/v1/products/?category_id={roofing.id}")

    assert product["category_ids"] == sorted([lumber.id, roofing.id])
    assert [p["id"] for p in response.json()] == [product["id"]]
