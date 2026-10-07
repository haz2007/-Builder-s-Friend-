from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Category, User
from ..schemas import CategoryBase, CategoryResponse


router = APIRouter(
    prefix="/api/v1/categories",
    tags=["Categories"]
)


@router.get("/", response_model=list[CategoryResponse])
def get_categories(
    db: Session = Depends(get_db)
):
    return db.query(Category).all()


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    category = (
        db.query(Category)
        .filter(Category.id == category_id)
        .first()
    )

    if category is None:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    return category


@router.post("/", response_model=CategoryResponse)
def create_category(
    category: CategoryBase,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    existing_category = (
        db.query(Category)
        .filter(Category.name == category.name)
        .first()
    )

    if existing_category:
        raise HTTPException(
            status_code=400,
            detail="Category already exists"
        )

    new_category = Category(
        name=category.name
    )

    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    return new_category


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    category_data: CategoryBase,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    category = (
        db.query(Category)
        .filter(Category.id == category_id)
        .first()
    )

    if category is None:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    existing_category = (
        db.query(Category)
        .filter(
            Category.name == category_data.name,
            Category.id != category_id
        )
        .first()
    )

    if existing_category:
        raise HTTPException(
            status_code=400,
            detail="Category already exists"
        )

    category.name = category_data.name

    db.commit()
    db.refresh(category)

    return category