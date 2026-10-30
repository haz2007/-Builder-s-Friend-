"""SEO: «шапка» страницы для поисковиков и карта сайта."""

import json
import re
from xml.etree import ElementTree

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Category, Product


def make_product(active=1, stock=100, category_name="Доска"):
    db = SessionLocal()
    category = Category(name=category_name)
    db.add(category)
    db.flush()
    product = Product(
        name="Доска обрезная 50×150×6000",
        description="Хвоя, для каркаса",
        price=620,
        stock_quantity=stock,
        unit="шт",
        category_id=category.id,
        is_active=active,
    )
    db.add(product)
    db.commit()
    ids = product.id, category.id
    db.close()
    return ids


def head(client, path):
    return client.get("/api/v1/seo/head", params={"path": path, "host": "builders-friend.ru"}).text


def json_ld(text, kind=None):
    """Разметка schema.org из шапки: первая или нужного типа."""
    blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text)]
    return next(b for b in blocks if kind is None or b["@type"] == kind)


def test_home_has_store_schema(client: TestClient):
    text = head(client, "/")

    assert "<title>Друг Строителя — доска, брус и крепёж в Химках</title>" in text
    assert json_ld(text, "WebSite")["name"] == "Друг Строителя"
    store = json_ld(text, "HardwareStore")
    assert store["telephone"] == ["+7 964 705-68-20", "+7 901 768-03-67"]
    assert store["geo"]["latitude"] == 55.976238
    assert 'og:image" content="https://builders-friend.ru/og-image.jpg"' in text


def test_product_page_has_title_price_and_availability(client: TestClient):
    product_id, _ = make_product()

    text = head(client, f"/product/{product_id}")

    assert "<title>Доска обрезная 50×150×6000 — купить в Химках | Друг Строителя</title>" in text
    assert "620 ₽ за шт" in text
    offer = json_ld(text, "Product")["offers"]
    assert offer["price"] == "620.00" and offer["priceCurrency"] == "RUB"
    assert offer["availability"].endswith("InStock")
    assert f'canonical" href="https://builders-friend.ru/product/{product_id}"' in text


def test_out_of_stock_and_hidden_products(client: TestClient):
    empty_id, _ = make_product(stock=0)
    assert json_ld(head(client, f"/product/{empty_id}"), "Product")["offers"]["availability"].endswith("OutOfStock")

    db = SessionLocal()
    db.get(Product, empty_id).is_active = 0
    db.commit()
    db.close()
    # Скрытый товар — как обычная страница, без разметки товара и закрыта от поиска
    hidden = head(client, f"/product/{empty_id}")
    assert "купить в Химках" not in hidden.split("</title>")[0]
    assert 'content="noindex, nofollow"' in hidden


def test_product_and_category_have_breadcrumbs(client: TestClient):
    db = SessionLocal()
    parent = Category(name="Пиломатериалы")
    db.add(parent)
    db.flush()
    child = Category(name="Доска", parent_id=parent.id)
    db.add(child)
    db.flush()
    db.add_all(
        [
            Product(name="Доска 25×100", price=480, stock_quantity=5, unit="шт", category_id=child.id, is_active=1),
            Product(name="Доска 50×150", price=920, stock_quantity=5, unit="шт", category_id=child.id, is_active=1),
        ]
    )
    db.commit()
    parent_id, child_id = parent.id, child.id
    product_id = db.query(Product.id).filter(Product.name == "Доска 25×100").scalar()
    db.close()

    crumbs = json_ld(head(client, f"/product/{product_id}"), "BreadcrumbList")["itemListElement"]
    assert [c["name"] for c in crumbs] == ["Каталог", "Пиломатериалы", "Доска", "Доска 25×100"]
    assert crumbs[1]["item"] == f"https://builders-friend.ru/catalog/{parent_id}"
    assert "item" not in crumbs[-1]

    # У верхнего раздела товары считаются вместе с подразделами
    text = head(client, f"/catalog/{parent_id}")
    assert "Пиломатериалы в Химках: 2 позиции, цены от 480 ₽" in text
    assert "noindex" not in text
    assert [c["name"] for c in json_ld(text, "BreadcrumbList")["itemListElement"]] == ["Каталог", "Пиломатериалы"]
    assert "Доска в Химках: 2 позиции" in head(client, f"/catalog/{child_id}")


def test_empty_category_and_unknown_pages_are_not_indexed(client: TestClient):
    db = SessionLocal()
    empty = Category(name="Вагонка")
    db.add(empty)
    db.commit()
    empty_id = empty.id
    db.close()

    assert 'content="noindex, nofollow"' in head(client, f"/catalog/{empty_id}")
    assert 'content="noindex, nofollow"' in head(client, "/account")
    assert 'content="noindex, nofollow"' in head(client, "/kontakty")
    assert "noindex" not in head(client, "/")
    assert f"/catalog/{empty_id}<" not in client.get("/api/v1/seo/sitemap.xml").text


def test_admin_is_not_indexed_and_text_is_escaped(client: TestClient):
    assert 'name="robots" content="noindex, nofollow"' in head(client, "/admin/orders")

    db = SessionLocal()
    category = Category(name="Доска <script>alert(1)</script>")
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


def test_yml_feed_lists_offers_with_price_picture_and_availability(client: TestClient):
    product_id, category_id = make_product()
    on_order_id, _ = make_product(stock=0, category_name="Брус")
    hidden_id, _ = make_product(active=0, category_name="Фанера")
    db = SessionLocal()
    db.get(Product, product_id).image_url = "/catalog/doska.webp"
    db.get(Product, on_order_id).name = 'Брус "сухой" & строганый'
    db.commit()
    db.close()

    response = client.get("/api/v1/seo/yml.xml", params={"host": "builders-friend.ru"})
    root = ElementTree.fromstring(response.content)

    assert response.headers["content-type"].startswith("application/xml")
    assert root.tag == "yml_catalog" and root.get("date")
    shop = root.find("shop")
    assert shop.findtext("name") == "Друг Строителя"
    assert shop.find(f"categories/category[@id='{category_id}']").text == "Доска"
    offers = {offer.get("id"): offer for offer in shop.iter("offer")}
    assert str(hidden_id) not in offers

    offer = offers[str(product_id)]
    assert offer.get("available") == "true"
    assert offer.findtext("url") == f"https://builders-friend.ru/product/{product_id}"
    assert offer.findtext("price") == "620.00"
    assert offer.findtext("currencyId") == "RUR"
    assert offer.findtext("categoryId") == str(category_id)
    assert offer.findtext("picture") == "https://builders-friend.ru/catalog/doska.webp"

    on_order = offers[str(on_order_id)]
    assert on_order.get("available") == "false"
    assert on_order.findtext("name") == 'Брус "сухой" & строганый'
    assert "&quot;сухой&quot; &amp;" in response.text
