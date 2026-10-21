"""Журнал действий в админке (таблица audit_log).

record() добавляет запись в текущую транзакцию — изменение и запись о нём
сохраняются вместе. changes_between() сравнивает «до» и «после» и сразу
готовит понятную строку для журнала.
"""

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog, Product, ProductVariant, User

PRODUCT_FIELDS = {
    "name": "название",
    "price": "цена",
    "stock_quantity": "остаток",
    "unit": "единица",
    "category_id": "категория",
    "description": "описание",
    "thickness_mm": "толщина",
    "width_mm": "ширина",
    "length_mm": "длина",
    "image_url": "фото",
    "is_active": "в каталоге",
}

VARIANT_FIELDS = {
    "name": "название",
    "unit": "единица",
    "price": "цена",
    "base_quantity": "коэффициент",
    "is_active": "активен",
}


def snapshot(obj: Any, fields: dict[str, str]) -> dict[str, Any]:
    return {field: getattr(obj, field) for field in fields}


def _show(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def changes_between(
    before: dict[str, Any], after: dict[str, Any], labels: dict[str, str]
) -> tuple[str, dict[str, list[Any]]]:
    """«цена 600 → 650; остаток 100 → 120» и {"price": [600, 650], …}."""
    changed = {field: [before[field], after[field]] for field in labels if before[field] != after[field]}
    parts = []
    for field, (old, new) in changed.items():
        if field == "description":
            parts.append("описание изменено")
        elif field == "image_url":
            parts.append("новое фото")
        else:
            parts.append(f"{labels[field]} {_show(old)} → {_show(new)}")
    return "; ".join(parts), changed


def diff(obj: Any, before: dict[str, Any], labels: dict[str, str]) -> tuple[str, dict[str, list[Any]]]:
    """Что изменилось у объекта с момента snapshot(): строка для журнала и было/стало."""
    return changes_between(before, snapshot(obj, labels), labels)


def record(
    db: Session,
    actor: User | None,
    action: str,
    entity: str,
    entity_id: int | None,
    summary: str,
    changes: dict | None = None,
) -> None:
    db.add(AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        entity=entity,
        entity_id=entity_id,
        summary=summary[:500],
        changes=changes or None,
    ))


def product_title(product: Product) -> str:
    return f"«{product.name}»"


def variant_title(product: Product, variant: ProductVariant) -> str:
    return f"«{product.name}», вариант «{variant.name}»"
