"""Поиск с опечатками на PostgreSQL (pg_trgm).

Обычный поиск — по словам (ILIKE). Если он ничего не нашёл — «досака»,
«обрезнаая доска», «вагонко», — сравниваем запрос с названиями по
триграммам: word_similarity ищет самое похожее место в названии.
Оператор %> с порогом 0,35 идёт по GIN-индексу ix_products_name_trgm.
"""

from typing import Any

from sqlalchemy import ColumnElement, func, text
from sqlalchemy.orm import Query, Session

from ..models import Product

SIMILARITY_THRESHOLD = 0.35


def fuzzy_query(db: Session, search: str) -> tuple[Query[Product], ColumnElement[Any]]:
    """Товары, похожие на запрос, и выражение похожести для сортировки."""
    phrase = " ".join(search.lower().replace("ё", "е").split())
    # Порог только для этой транзакции; по умолчанию у pg_trgm 0,6 — слишком строго
    db.execute(text(f"SET LOCAL pg_trgm.word_similarity_threshold = {SIMILARITY_THRESHOLD}"))
    name = func.lower(Product.name)
    similarity = func.word_similarity(phrase, name)
    query = db.query(Product).filter(name.op("%>")(phrase))
    return query, similarity


def suggestions(db: Session, search: str, limit: int = 5) -> list[tuple[Product, float]]:
    """«Возможно, вы искали»: самые похожие названия из каталога."""
    query, similarity = fuzzy_query(db, search)
    rows = (
        query.add_columns(similarity)
        .filter(Product.is_active == 1)
        .order_by(similarity.desc(), Product.name)
        .limit(limit)
        .all()
    )
    return [(product, round(float(score), 2)) for product, score in rows]
