from fastapi.testclient import TestClient

from app.auth import hash_password, phone_variants
from app.database import SessionLocal
from app.models import User


def create_user(**fields):
    db = SessionLocal()

    user = User(password_hash=hash_password("password123"), **fields)

    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    return user


def test_phone_variants_cover_russian_formats():
    variants = phone_variants("8 (999) 123-45-67")

    assert "+79991234567" in variants
    assert "89991234567" in variants
    assert "9991234567" in variants


def test_login_with_8_when_registered_with_plus_7(client: TestClient):
    create_user(phone="+79991234567", role="CUSTOMER")

    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "8 999 123-45-67", "password": "password123"},
    )

    assert response.status_code == 200


def test_register_rejects_same_number_in_other_format(client: TestClient):
    create_user(phone="+79991234567", role="CUSTOMER")

    response = client.post(
        "/api/v1/auth/register",
        json={"phone": "89991234567", "password": "secret-pass", "privacy_accepted": True},
    )

    assert response.status_code == 400


def test_admin_email_login_ignores_case(client: TestClient):
    create_user(email="owner@woodcommerce.local", role="ADMIN")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "Owner@WoodCommerce.local ", "password": "password123"},
    )

    assert response.status_code == 200


def test_wrong_password_still_rejected(client: TestClient):
    create_user(phone="+79991234567", role="CUSTOMER")

    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "89991234567", "password": "wrong"},
    )

    assert response.status_code == 401
