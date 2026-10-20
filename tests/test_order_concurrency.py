from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, User


def setup_products():
    db = SessionLocal()
    customer = User(phone="+79990001122", password_hash=hash_password("x"), role="CUSTOMER")
    category = Category(name="Пиломатериалы")
    db.add_all([customer, category])
    db.commit()
    board = Product(name="Доска", price=600, stock_quantity=1000, unit="шт", category_id=category.id)
    beam = Product(name="Брус", price=900, stock_quantity=1000, unit="шт", category_id=category.id)
    db.add_all([board, beam])
    db.commit()
    data = (
        {"Authorization": f"Bearer {create_access_token(user_id=customer.id, role='CUSTOMER')}"},
        board.id,
        beam.id,
    )
    db.close()
    return data


def get_stock(product_id):
    db = SessionLocal()
    stock = db.get(Product, product_id).stock_quantity
    db.close()
    return stock


def test_parallel_orders_with_reversed_items_do_not_deadlock(client: TestClient):
    headers, board_id, beam_id = setup_products()

    def place(first, second):
        return client.post(
            "/api/v1/orders/",
            json={
                "customer_name": "Покупатель",
                "delivery_method": "PICKUP",
                "items": [
                    {"product_id": first, "quantity": 1},
                    {"product_id": second, "quantity": 1},
                ],
            },
            headers=headers,
        ).status_code

    # Половина заказов кладёт товары в одном порядке, половина — в обратном
    jobs = [(board_id, beam_id) if index % 2 else (beam_id, board_id) for index in range(20)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda pair: place(*pair), jobs))

    assert statuses == [200] * 20
    # Каждый заказ списал ровно по одной штуке каждого товара
    assert get_stock(board_id) == 980
    assert get_stock(beam_id) == 980
