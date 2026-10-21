"""SEO: «шапка» страницы для поисковиков и карта сайта."""

import json
import re

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Category, Product


def make_product(active=1, stock=100, category_name="Доска"):
    db = SessionLocal()
    category = Category(name=category_name)
    db.add(category)
    db.flush()
    product = Product(name="Доска обрезная 50×150×6000", description="Хвоя, для каркаса",
                      price=620, stock_quantity=stock, unit="шт", category_id=category.id, is_active=active)
    db.add(product)
    db.commit()
    ids = product.id, category.id
    db.close()
    return ids


def head(client, path):
    return client.get("/api/v1/seo/head", params={"path": path, "host": "builders-friend.ru"}).text


def json_ld(text):
    return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', text).group(1))


def test_home_has_store_schema(client: TestClient):
    text = head(client, "/")

    assert "<title>Друг Строителя — доска, брус и крепёж в Химках</title>" in text
    store = json_ld(text)
    assert store["@type"] == "HardwareStore"
    assert store["telephone"] == ["+7 964 705-68-20", "+7 901 768-03-67"]
    assert store["geo"]["latitude"] == 55.976238
    assert 'og:image" content="https://builders-friend.ru/og-image.jpg"' in text


def test_product_page_has_title_price_and_availability(client: TestClient):
    product_id, _ = make_product()

    text = head(client, f"/product/{product_id}")

    assert "<title>Доска обрезная 50×150×6000 — купить в Химках | Друг Строителя</title>" in text
    assert "620 ₽ за шт" in text
    offer = json_ld(text)["offers"]
    assert offer["price"] == "620.00" and offer["priceCurrency"] == "RUB"
    assert offer["availability"].endswith("InStock")
    assert f'canonical" href="https://builders-friend.ru/product/{product_id}"' in text


def test_out_of_stock_and_hidden_products(client: TestClient):
    empty_id, _ = make_product(stock=0)
    assert json_ld(head(client, f"/product/{empty_id}"))["offers"]["availability"].endswith("OutOfStock")

    db = SessionLocal()
    db.get(Product, empty_id).is_active = 0
    db.commit()
    db.close()
    # Скрытый товар — как обычная страница, без разметки товара
    assert "купить в Химках" not in head(client, f"/product/{empty_id}").split("</title>")[0]


def test_admin_is_not_indexed_and_text_is_escaped(client: TestClient):
    assert 'name="robots" content="noindex, nofollow"' in head(client, "/admin/orders")

    db = SessionLocal()
    category = Category(name='Доска <script>alert(1)</script>')
    db.add(category)
    db.commit()
    category_id = category.id
    db.close()
    assert "<script>alert" not in head(client, f"/catalog/{category_id}")


def test_sitemap_lists_active_products_and_categories(client: TestClient):
    product_id, category_id = make_product()
    hidden_id, _ = make_product(active=0, category_name="Брус")

    xml = client.get("/api/v1/seo/sitemap.xml", params={"host": "builders-friend.ru"}).text

    assert "<loc>https://builders-friend.ru/</loc>" in xml
    assert f"<loc>https://builders-friend.ru/product/{product_id}</loc>" in xml
    assert f"<loc>https://builders-friend.ru/catalog/{category_id}</loc>" in xml
    assert f"/product/{hidden_id}<" not in xml


def test_host_is_sanitized(client: TestClient):
    text = client.get("/api/v1/seo/head", params={"path": "/", "host": 'evil.ru"><script>'}).text
    assert '"><script>' not in text
