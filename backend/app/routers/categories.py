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