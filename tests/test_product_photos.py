"""Фото товара: уменьшается, пересохраняется в WebP, теряет EXIF (и GPS)."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, User
from app.routers import products as products_router


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(products_router, "UPLOAD_DIR", tmp_path)
    return tmp_path


def admin_and_product():
    db = SessionLocal()
    admin = User(email="admin@woodcommerce.local", password_hash=hash_password("x" * 8), role="ADMIN")
    category = Category(name="Доска")
    db.add_all([admin, category])
    db.flush()
    product = Product(name="Доска", price=600, stock_quantity=10, unit="шт", category_id=category.id)
    db.add(product)
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user_id=admin.id, role='ADMIN')}"}
    product_id = product.id
    db.close()
    return headers, product_id


def phone_photo() -> bytes:
    """Как с телефона: 4000×3000, поворот в EXIF и координаты."""
    image = Image.new("RGB", (4000, 3000), (180, 120, 60))
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: повернуть на 90°
    exif[0x8825] = {1: "N", 2: (55.0, 58.0, 34.0)}  # GPS
    data = io.BytesIO()
    image.save(data, "JPEG", quality=95, exif=exif)
    return data.getvalue()


def upload(client, headers, product_id, contents, name="photo.jpg"):
    return client.post(
        f"/api/v1/products/{product_id}/image",
        files={"file": (name, contents, "image/jpeg")},
        headers=headers,
    )


def test_phone_photo_is_shrunk_rotated_and_stripped(client: TestClient, upload_dir):
    headers, product_id = admin_and_product()
    original = phone_photo()

    response = upload(client, headers, product_id, original)

    assert response.status_code == 200
    assert response.json()["image_url"].endswith(".webp")
    saved = next(upload_dir.iterdir())
    assert saved.stat().st_size < len(original) / 5
    with Image.open(saved) as image:
        assert image.format == "WEBP"
        # Повёрнуто по EXIF: была альбомная 4000×3000, стала книжная
        assert image.size == (1200, 1600)
        assert not image.getexif()


def test_not_an_image_is_rejected(client: TestClient, upload_dir):
    headers, product_id = admin_and_product()

    response = upload(client, headers, product_id, b"not an image", name="price.txt")

    assert response.status_code == 400
    assert list(upload_dir.iterdir()) == []


def test_transparent_png_keeps_transparency(client: TestClient, upload_dir):
    headers, product_id = admin_and_product()
    data = io.BytesIO()
    Image.new("RGBA", (300, 200), (0, 0, 0, 0)).save(data, "PNG")

    assert upload(client, headers, product_id, data.getvalue(), name="logo.png").status_code == 200
    with Image.open(next(upload_dir.iterdir())) as image:
        assert image.mode == "RGBA"
