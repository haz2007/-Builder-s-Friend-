from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token,
    hash_password,
    verify_password,
    get_current_user
)
from ..database import get_db
from ..models import User
from ..schemas import (
    LoginRequest,
    TokenResponse,
    UserRegister,
    UserResponse
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)


@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
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

    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role="CUSTOMER"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email == login_data.email)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        login_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = create_access_token(
        user_id=user.id,
        role=user.role
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user