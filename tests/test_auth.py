def test_register(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "pytest_user@woodcommerce.local",
            "password": "123456"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "pytest_user@woodcommerce.local"
    assert data["role"] == "CUSTOMER"
    assert "password" not in data
    assert "password_hash" not in data


def test_login(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "pytest_login@woodcommerce.local",
            "password": "123456"
        }
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "pytest_login@woodcommerce.local",
            "password": "123456"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_with_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "pytest_wrong_password@woodcommerce.local",
            "password": "123456"
        }
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "pytest_wrong_password@woodcommerce.local",
            "password": "wrong_password"
        }
    )

    assert response.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    