"""Пробные товары с вариантами продажи (штука / куб / пачка / коробка).

Запуск: .venv/bin/python seed_demo.py
Повторный запуск безопасен: товары с такими же названиями пропускаются.
"""

from app.database import SessionLocal
from app.models import Category, Product, ProductVariant
from app.services.variant_service import recalc_cubic_variants, sync_product_from_primary

# name, category, description, unit, stock, dimensions (мм) или None,
# варианты: (название, единица, цена, сколько базовых единиц в 1 единице)
DEMO_PRODUCTS = [
    (
        "Доска обрезная 50×150×6000",
        "Пиломатериалы/Доска",
        "Хвоя, естественной влажности. Для каркаса, перекрытий и стропил.",
        "шт", 440, (50, 150, 6000),
        [("Штука", "шт", 620, 1), ("Куб", "м3", 13500, None)],
    ),
    (
        "Доска обрезная 40×150×6100",
        "Пиломатериалы/Доска",
        "Сосна, 1 сорт. В кубе 27 досок (27,33 округляется вниз).",
        "шт", 300, (40, 150, 6100),
        [("Штука", "шт", 560, 1), ("Куб", "м3", 14800, None)],
    ),
    (
        "Брус 100×100×6000",
        "Пиломатериалы/Брус",
        "Строганый брус для стен, балок и опор.",
        "шт", 160, (100, 100, 6000),
        [("Штука", "шт", 950, 1), ("Куб", "м3", 15000, None)],
    ),
    (
        "Вагонка 12,5×96×3000",
        "Пиломатериалы/Вагонка",
        "Сорт «В», для внутренней отделки стен и потолков.",
        "шт", 600, (12.5, 96, 3000),
        [("Штука", "шт", 120, 1), ("Пачка 10 шт", "пачка", 1150, 10), ("Куб", "м3", 30000, None)],
    ),
    (
        "Саморезы по дереву 3,5×35",
        "Крепёж/Саморезы",
        "Жёлтый цинк, потай. Около 870 штук в килограмме.",
        "кг", 120, None,
        [("Килограмм", "кг", 450, 1), ("Коробка 5 кг", "коробка", 2100, 5)],
    ),
    (
        "Гвозди строительные 100 мм",
        "Крепёж/Гвозди",
        "Чёрные, ГОСТ 4028-63.",
        "кг", 200, None,
        [("Килограмм", "кг", 180, 1), ("Ящик 25 кг", "ящик", 4200, 25)],
    ),
    (
        "ОСБ-3 9 мм 1250×2500",
        "Листовые материалы/ОСБ",
        "Влагостойкая плита для обшивки и черновых полов.",
        "лист", 80, None,
        [("Лист", "лист", 690, 1), ("Пачка 10 листов", "пачка", 6600, 10)],
    ),
    (
        "Доска обрезная 25×100×6000",
        "Пиломатериалы/Доска",
        "Тонкая доска для обрешётки, опалубки и подшивки.",
        "шт", 700, (25, 100, 6000),
        [("Штука", "шт", 210, 1), ("Куб", "м3", 13000, None)],
    ),
    (
        "Брусок 50×50×3000",
        "Пиломатериалы/Брус",
        "Для обрешётки, лаг и каркасов перегородок.",
        "шт", 900, (50, 50, 3000),
        [("Штука", "шт", 140, 1), ("Куб", "м3", 14500, None)],
    ),
    (
        "Брус 150×150×6000",
        "Пиломатериалы/Брус",
        "Брус для стен бани и дома, опорных балок.",
        "шт", 90, (150, 150, 6000),
        [("Штука", "шт", 2100, 1), ("Куб", "м3", 15500, None)],
    ),
    (
        "Саморезы кровельные 4,8×35",
        "Крепёж/Саморезы",
        "С прессшайбой и EPDM-прокладкой, для профлиста и металлочерепицы.",
        "кг", 60, None,
        [("Килограмм", "кг", 520, 1), ("Коробка 5 кг", "коробка", 2450, 5)],
    ),
    (
        "Гвозди финишные 50 мм",
        "Крепёж/Гвозди",
        "Оцинкованные, с маленькой шляпкой — для вагонки и плинтуса.",
        "кг", 80, None,
        [("Килограмм", "кг", 260, 1), ("Коробка 5 кг", "коробка", 1200, 5)],
    ),
    (
        "Фанера ФК 10 мм 1525×1525",
        "Листовые материалы/Фанера",
        "Берёзовая фанера, сорт 3/4. Для мебели, полов и перегородок.",
        "лист", 60, None,
        [("Лист", "лист", 1150, 1), ("Пачка 10 листов", "пачка", 11000, 10)],
    ),
]

# Фото с Unsplash (бесплатная лицензия, подключаются ссылкой)
PHOTOS = {
    "Доска обрезная 50×150×6000": "1681752972950-6229ca099fbc",
    "Доска обрезная 40×150×6100": "1634672652995-ee7525bce595",
    "Доска обрезная 25×100×6000": "1561435354-298941a0d4a2",
    "Брус 100×100×6000": "1590635022668-81cc8696a19d",
    "Брус 150×150×6000": "1563874093519-ca5eda5cd776",
    "Брусок 50×50×3000": "1533541268314-af6680461b41",
    "Вагонка 12,5×96×3000": "1675528030748-d463ab87e8d5",
    "Саморезы по дереву 3,5×35": "1640958899295-957d780644e7",
    "Саморезы кровельные 4,8×35": "1602146796053-4ce0a5763b2e",
    "Гвозди строительные 100 мм": "1571505280193-4b4e29712a77",
    "Гвозди финишные 50 мм": "1640958899091-a1f55539eac0",
    "ОСБ-3 9 мм 1250×2500": "1758749130179-46ebeba477bb",
    "Фанера ФК 10 мм 1525×1525": "1690768162439-7ca7a1813038",
}


def photo_url(name: str) -> str | None:
    photo_id = PHOTOS.get(name)
    if photo_id is None:
        return None
    return f"https://images.unsplash.com/photo-{photo_id}?auto=format&fit=crop&w=900&q=80"


def get_category(db, path: str) -> Category:
    """«Пиломатериалы/Доска» → подкатегория «Доска» внутри «Пиломатериалы»."""
    parent = None
    for name in path.split("/"):
        category = db.query(Category).filter(Category.name == name).first()
        if category is None:
            category = Category(name=name, parent_id=parent.id if parent else None)
            db.add(category)
            db.flush()
        parent = category
    return parent


def seed() -> None:
    db = SessionLocal()
    created = 0
    try:
        for name, category_name, description, unit, stock, dims, variants in DEMO_PRODUCTS:
            category = get_category(db, category_name)

            existing = db.query(Product).filter(Product.name == name).first()
            if existing and photo_url(name) and not (existing.image_url or "").startswith("/uploads/"):
                # Своё загруженное фото не трогаем, ссылку Unsplash — обновляем
                existing.image_url = photo_url(name)
            if existing:
                # Переносим уже добавленный товар в подкатегорию
                if existing.category_id != category.id:
                    existing.category_id = category.id
                    existing.categories = [category]
                    print(f"~ {name}: перенесён в «{category_name}»")
                else:
                    print(f"— уже есть: {name}")
                continue

            product = Product(
                name=name,
                description=description,
                price=variants[0][2],
                stock_quantity=stock,
                unit=unit,
                category_id=category.id,
                is_active=1,
                image_url=photo_url(name),
            )
            if dims:
                product.thickness_mm, product.width_mm, product.length_mm = dims
            product.categories = [category]

            for variant_name, variant_unit, price, base in variants:
                product.variants.append(ProductVariant(
                    name=variant_name,
                    unit=variant_unit,
                    price=price,
                    base_quantity=base or 1,
                    is_active=1,
                ))

            # «Куб» сам получит число досок в 1 м³ по размерам
            recalc_cubic_variants(product)
            sync_product_from_primary(product)
            db.add(product)
            db.flush()
            created += 1

            summary = ", ".join(
                f"{v.name} {v.price:g} ₽" + (f" (= {v.base_quantity:g} {unit})" if v.base_quantity != 1 else "")
                for v in product.variants
            )
            print(f"+ {name}: {summary}")

        db.commit()
        print(f"Готово, добавлено товаров: {created}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
