"""Покупатель удаляет аккаунт сам: данные удаляются, заказы остаются для учёта."""

from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import AuditLog, Category, Order, Product, TelegramAccountLink, User

PHONE = "+79994445566"


def make_customer(with_order=False, role="CUSTOMER"):
    db = SessionLocal()
    user = User(phone=PHONE, password_hash=hash_password("my-password"), role=role)
    db.add(user)
    db.flush()
    db.add(TelegramAccountLink(user_id=user.id, telegram_user_id=555, telegram_chat_id=555))
    if with_order:
        category = Category(name="Доска")
        db.add(category)
        db.flush()
        db.add(Product(name="Доска", price=600, stock_quantity=5, unit="шт", category_id=category.id))
        db.add(Order(user_id=user.id, customer_name="Сергей", status="DELIVERED", total_price=600,
                     delivery_method="PICKUP", delivery_address="Самовывоз со склада"))
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user_id=user.id, role=role)}"}
    user_id = user.id
    db.close()
    return user_id, headers


def delete(client, headers, password="my-password"):
    return client.post("/api/v1/auth/delete-account", json={"password": password}, headers=headers)


def test_account_without_orders_is_deleted_completely(client: TestClient):
    user_id, headers = make_customer()

    assert delete(client, headers).status_code == 200

    db = SessionLocal()
    assert db.get(User, user_id) is None
    assert db.query(TelegramAccountLink).count() == 0
    assert db.query(AuditLog).filter(AuditLog.action == "user.deleted").count() == 1
    db.close()


def test_orders_stay_but_account_is_anonymized(client: TestClient):
    user_id, headers = make_customer(with_order=True)

    assert delete(client, headers).status_code == 200

    db = SessionLocal()
    user = db.get(User, user_id)
    assert user.phone is None and user.email is None
    assert db.query(Order).filter(Order.user_id == user_id).count() == 1
    db.close()
    # Ни войти по телефону, ни пользоваться старым токеном
    assert client.post("/api/v1/auth/login", json={"phone": PHONE, "password": "my-password"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    # Номер свободен — можно зарегистрироваться заново
    register = {"phone": PHONE, "password": "new-password", "privacy_accepted": True}
    again = client.post("/api/v1/auth/register", json=register)
    assert again.status_code == 200


def test_wrong_password_and_admins_are_refused(client: TestClient):
    _, headers = make_customer()
    assert delete(client, headers, password="wrong").status_code == 400

    db = SessionLocal()
    db.query(TelegramAccountLink).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    _, admin_headers = make_customer(role="ADMIN")
    assert delete(client, admin_headers).status_code == 400
