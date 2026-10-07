from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin
from ..database import get_db
from ..models import User
from ..schemas import UserCreate, UserResponse


router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"]
)


@router.get("/", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    return db.query(User).all()


@router.post("/drivers", response_model=UserResponse)
def create_driver(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists"
        )

    driver = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role="DRIVER"
    )

    db.add(driver)
    db.commit()
    db.refresh(driver)

    return driver


@router.patch("/{user_id}/role", response_model=UserResponse)
def change_user_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    allowed_roles = {
        "CUSTOMER",
        "DRIVER",
        "ADMIN"
    }

    if role not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail="Invalid role"
        )

    user.role = role

    db.commit()
    db.refresh(user)

    return user