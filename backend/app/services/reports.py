"""Аналитические отчёты на чистом SQL.

Запросы лежат в app/sql/*.sql: агрегаты, CTE (в том числе рекурсивный) и
оконные функции считает PostgreSQL, Python только подставляет параметры и
приводит NUMERIC к float для JSON. Разбор запросов и планы — docs/sql/README.md.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


@lru_cache
def load_sql(name: str):
    return text((SQL_DIR / f"{name}.sql").read_text(encoding="utf-8"))


def _plain(value):
    """NUMERIC → float, даты → ISO-строки: результат сразу готов для JSON."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def run(db: Session, name: str, **params) -> list[dict]:
    rows = db.execute(load_sql(name), params).mappings().all()
    return [{key: _plain(value) for key, value in row.items()} for row in rows]


def period_params(start: datetime | None, end: datetime | None) -> dict:
    return {"period_start": start, "period_end": end}


def revenue_by_period(
    db: Session, start: datetime | None, end: datetime | None, granularity: str
) -> list[dict]:
    # end — полночь после периода, последняя корзина — по последнему дню
    last_day = end - timedelta(days=1) if end else None
    return run(
        db,
        "revenue_by_period",
        unit=granularity,
        last_day=last_day,
        **period_params(start, end),
    )


def category_revenue(db: Session, start: datetime | None, end: datetime | None) -> list[dict]:
    return run(db, "category_revenue", **period_params(start, end))


def product_abc(db: Session, start: datetime | None, end: datetime | None) -> list[dict]:
    return run(db, "product_abc", **period_params(start, end))


def monthly_summary(db: Session, today: date) -> list[dict]:
    return run(db, "monthly_summary", today=datetime.combine(today, datetime.min.time()))


def repeat_customers(db: Session) -> dict:
    return run(db, "repeat_customers")[0]
