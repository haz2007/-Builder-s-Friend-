from app.database import SessionLocal
from app.models import User
from app.auth import hash_password


def test_register(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "phone": "+79991110001",
            "password": "12345678",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["phone"] == "+79991110001"
    assert data["role"] == "CUSTOMER"
    assert "password" not in data
    assert "password_hash" not in data


def test_login(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "phone": "+79991110002",
            "password": "12345678",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "phone": "+79991110002",
            "password": "12345678",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_with_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "phone": "+79991110003",
            "password": "12345678",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "phone": "+79991110003",
            "password": "wrong_password",
        },
    )

    assert response.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
