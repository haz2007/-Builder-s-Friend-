"""Сброс пароля: код из Telegram-бота и временный пароль от администратора."""

import re

import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import PasswordResetCode, TelegramAccountLink, User
from app.services import password_reset

PHONE = "+79991112233"


@pytest.fixture
def telegram(monkeypatch):
    """Перехватывает сообщения бота вместо отправки в Telegram."""
    sent = []
    monkeypatch.setattr(password_reset, "send_telegram_message", lambda chat_id, text: sent.append((chat_id, text)))
    return sent


def make_user(role="CUSTOMER", linked=True, phone=PHONE, **fields):
    db = SessionLocal()
    user = User(phone=phone, password_hash=hash_password("old-password"), role=role, **fields)
    db.add(user)
    db.flush()
    if linked:
        db.add(TelegramAccountLink(user_id=user.id, telegram_user_id=777, telegram_chat_id=777))
    db.commit()
    user_id = user.id
    db.close()
    return user_id


def code_from(sent):
    return re.search(r"\b(\d{6})\b", sent[-1][1]).group(1)


def test_code_comes_to_telegram_and_changes_password(client: TestClient, telegram):
    make_user()

    response = client.post("/api/v1/auth/password-reset/request", json={"phone": "8 999 111-22-33"})
    assert response.status_code == 200
    assert telegram[0][0] == 777

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"phone": PHONE, "code": code_from(telegram), "new_password": "new-password-1"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]

    login = client.post("/api/v1/auth/login", json={"phone": PHONE, "password": "new-password-1"})
    assert login.status_code == 200
    old = client.post("/api/v1/auth/login", json={"phone": PHONE, "password": "old-password"})
    assert old.status_code == 401


def test_same_answer_for_unknown_and_unlinked_numbers(client: TestClient, telegram):
    make_user(linked=False)

    unknown = client.post("/api/v1/auth/password-reset/request", json={"phone": "+79990000000"})
    unlinked = client.post("/api/v1/auth/password-reset/request", json={"phone": PHONE})

    assert unknown.json() == unlinked.json()
    assert telegram == []


def test_code_is_single_use_and_stored_as_hash(client: TestClient, telegram):
    make_user()
    client.post("/api/v1/auth/password-reset/request", json={"phone": PHONE})
    code = code_from(telegram)

    db = SessionLocal()
    stored = db.query(PasswordResetCode).one().code_hash
    db.close()
    assert code not in stored

    body = {"phone": PHONE, "code": code, "new_password": "new-password-1"}
    assert client.post("/api/v1/auth/password-reset/confirm", json=body).status_code == 200
    assert client.post("/api/v1/auth/password-reset/confirm", json=body).status_code == 400


def test_five_wrong_codes_burn_the_code(client: TestClient, telegram):
    make_user()
    client.post("/api/v1/auth/password-reset/request", json={"phone": PHONE})
    real = code_from(telegram)
    wrong = "000000" if real != "000000" else "111111"

    for _ in range(5):
        response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"phone": PHONE, "code": wrong, "new_password": "new-password-1"},
        )
        assert response.status_code == 400

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"phone": PHONE, "code": real, "new_password": "new-password-1"},
    )
    assert response.status_code == 400


def test_requests_are_rate_limited(client: TestClient, telegram):
    for _ in range(3):
        assert client.post("/api/v1/auth/password-reset/request", json={"phone": PHONE}).status_code == 200

    assert client.post("/api/v1/auth/password-reset/request", json={"phone": PHONE}).status_code == 429


def admin_headers():
    admin_id = make_user(role="ADMIN", linked=False, phone="+79990000099")
    return {"Authorization": f"Bearer {create_access_token(user_id=admin_id, role='ADMIN')}"}


def test_admin_gives_temporary_password_to_customer(client: TestClient):
    customer_id = make_user(linked=False)

    response = client.post(f"/api/v1/users/{customer_id}/reset-password", headers=admin_headers())

    password = response.json()["temporary_password"]
    assert len(password) == 8
    assert client.post("/api/v1/auth/login", json={"phone": PHONE, "password": password}).status_code == 200


def test_admin_cannot_reset_another_admin(client: TestClient):
    headers = admin_headers()
    other_admin = make_user(role="ADMIN", linked=False, phone="+79990000098", email="other@woodcommerce.local")

    response = client.post(f"/api/v1/users/{other_admin}/reset-password", headers=headers)

    assert response.status_code == 400


def test_customer_cannot_reset_passwords(client: TestClient):
    customer_id = make_user(linked=False)
    headers = {"Authorization": f"Bearer {create_access_token(user_id=customer_id, role='CUSTOMER')}"}

    assert client.post(f"/api/v1/users/{customer_id}/reset-password", headers=headers).status_code == 403
