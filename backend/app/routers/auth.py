
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token,
    find_user_by_email,
    find_user_by_phone,
    hash_password,
    verify_password,
    get_current_user,
)
from ..database import get_db
from ..models import User
from ..schemas import (
    LoginRequest,
    TokenResponse,
    UserRegister,
    UserResponse,
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


def normalize_phone(phone: str) -> str:
    """Удаляет пробелы и разделители из номера телефона."""
    normalized = re.sub(r"[\s()\-]", "", phone.strip())

    if not re.fullmatch(r"\+?\d{10,15}", normalized):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid phone number with 10 to 15 digits",
        )

    return normalized


@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    phone = normalize_phone(user_data.phone)

    existing_user = find_user_by_phone(db, phone)

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this phone number already exists",
        )

    user = User(
        phone=phone,
        password_hash=hash_password(user_data.password),
        role="CUSTOMER",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    # Нужно указать ровно один идентификатор: email или телефон.
    if bool(login_data.email) == bool(login_data.phone):
        raise HTTPException(
            status_code=400,
            detail="Provide either email or phone number",
        )

    if login_data.phone:
        phone = normalize_phone(login_data.phone)

        user = find_user_by_phone(db, phone)

        error_message = "Invalid phone number or password"

    else:
        user = find_user_by_email(db, login_data.email)

        error_message = "Invalid email or password"

    if user is None or not verify_password(
        login_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail=error_message,
        )

    # Не разрешаем покупателю войти в административную панель
    # только потому, что он знает email другого аккаунта.
    if login_data.email and user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Email login is reserved for administrators",
        )

    token = create_access_token(
        user_id=user.id,
        role=user.role,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user
