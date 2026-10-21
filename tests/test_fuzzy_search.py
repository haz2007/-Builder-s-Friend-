"""Поиск с опечатками (pg_trgm): «досака» → «Доска обрезная»."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal
from app.models import Category, Product

NAMES = ["Доска обрезная 50×150×6000", "Брус 100×100×6000", "Вагонка 12,5×96×3000", "Саморезы по дереву 4,2×75"]


@pytest.fixture
def catalog(reset_database):
    db = SessionLocal()
    category = Category(name="Всё")
    db.add(category)
    db.flush()
    db.add_all(
        Product(name=name, price=100, stock_quantity=10, unit="шт", category_id=category.id, is_active=1)
        for name in NAMES
    )
    db.add(Product(name="Доска скрытая", price=1, stock_quantity=1, unit="шт", category_id=category.id, is_active=0))
    db.commit()
    db.close()


def suggest(client, query):
    return [item["name"] for item in client.get("/api/v1/products/suggest", params={"q": query}).json()]


@pytest.mark.parametrize(
    ("typo", "expected"),
    [("досака", NAMES[0]), ("обрезнаая", NAMES[0]), ("вагонко", NAMES[2]), ("самарезы", NAMES[3]), ("бруус", NAMES[1])],
)
def test_typos_find_the_product(client: TestClient, catalog, typo, expected):
    assert suggest(client, typo)[0] == expected


def test_unrelated_word_finds_nothing_and_hidden_products_are_skipped(client: TestClient, catalog):
    assert suggest(client, "холодильник") == []
    assert "Доска скрытая" not in suggest(client, "доска")


def test_index_is_used_by_the_query(catalog):
    db = SessionLocal()
    db.execute(text("SET LOCAL enable_seqscan = off"))
    db.execute(text("SET LOCAL pg_trgm.word_similarity_threshold = 0.35"))
    plan = "\n".join(
        row[0] for row in db.execute(text("EXPLAIN SELECT id FROM products WHERE lower(name) %> 'досака'"))
    )
    db.close()
    assert "ix_products_name_trgm" in plan
