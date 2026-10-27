from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Category, Product, User
from ..schemas import CategoryInput, CategoryResponse
from ..services import audit

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])


def category_with_children_ids(db: Session, category_id: int) -> list[int]:
    """Категория и её подкатегории — для фильтра товаров."""
    child_ids = [
        child_id
        for (child_id,) in db.query(Category.id).filter(Category.parent_id == category_id)
    ]
    return [category_id, *child_ids]


def validate_parent(db: Session, parent_id: int | None, category_id: int | None = None) -> None:
    """Только два уровня: родитель должен быть категорией верхнего уровня."""
    if parent_id is None:
        return

    if parent_id == category_id:
        raise HTTPException(status_code=400, detail="Категория не может быть своим же родителем")

    parent = db.get(Category, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Родительская категория не найдена")

    if parent.parent_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Подкатегорию нельзя сделать родителем: допускается только два уровня",
        )

    if category_id is not None:
        has_children = db.query(Category).filter(Category.parent_id == category_id).first()
        if has_children:
            raise HTTPException(
                status_code=400,
                detail="У категории есть подкатегории — её нельзя вложить в другую",
            )


@router.get("/", response_model=list[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    return (
        db.query(Category)
        .order_by(Category.parent_id.isnot(None), Category.position, Category.name)
        .all()
    )


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.post("/", response_model=CategoryResponse)
def create_category(
    category: CategoryInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing_category = db.query(Category).filter(Category.name == category.name).first()
    if existing_category:
        raise HTTPException(status_code=400, detail="Category already exists")

    validate_parent(db, category.parent_id)

    new_category = Category(name=category.name, parent_id=category.parent_id)
    if category.position is not None:
        new_category.position = category.position
    db.add(new_category)
    db.flush()
    audit.record(db, current_user, "category.created", "category", new_category.id,
                 f"Добавлена категория «{new_category.name}»")
    db.commit()
    db.refresh(new_category)
    return new_category


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    category_data: CategoryInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    existing_category = db.query(Category).filter(
        Category.name == category_data.name,
        Category.id != category_id,
    ).first()
    if existing_category:
        raise HTTPException(status_code=400, detail="Category already exists")

    old_name, old_parent = category.name, category.parent_id
    category.name = category_data.name

    # Родителя меняем, только если его прислали явно (переименование не трогает)
    if "parent_id" in category_data.model_fields_set:
        validate_parent(db, category_data.parent_id, category_id)
        category.parent_id = category_data.parent_id

    if category_data.position is not None:
        category.position = category_data.position

    if (old_name, old_parent) != (category.name, category.parent_id):
        detail = f"«{old_name}» → «{category.name}»" if old_name != category.name else f"«{category.name}»"
        if old_parent != category.parent_id:
            detail += ", перенесена в другой раздел"
        audit.record(db, current_user, "category.updated", "category", category.id, f"Категория {detail}")

    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    children_count = db.query(Category).filter(Category.parent_id == category_id).count()
    if children_count:
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя удалить категорию: в ней есть подкатегории ({children_count}).",
        )

    products_count = db.query(Product).filter(Product.category_id == category_id).count()
    if products_count:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Нельзя удалить категорию: в ней осталось товаров: {products_count}. "
                "Сначала переместите товары в другую категорию."
            ),
        )

    audit.record(db, current_user, "category.deleted", "category", category.id,
                 f"Удалена категория «{category.name}»")
    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}
