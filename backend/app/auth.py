import os
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

SECRET_KEY = os.getenv("SECRET_KEY") or ""

if not SECRET_KEY:
    # На сервере без настоящего ключа любой мог бы подделать токен входа
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError("Задай SECRET_KEY в окружении: без него запуск на сервере запрещён")
    SECRET_KEY = "super_secure_lumber_secret_key_change_me"  # только для разработки

def phone_variants(phone: str) -> list[str]:
    """Все записи одного российского номера: +7…, 7…, 8… и 10 цифр.

    Пользователь мог зарегистрироваться с «+7 999…», а входить с «8999…».
    """
    raw = "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")
    digits = raw.lstrip("+")
    variants = {raw, digits, f"+{digits}"}

    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]

    if len(digits) == 10:
        variants |= {f"+7{digits}", f"7{digits}", f"8{digits}", digits}

    return sorted(variant for variant in variants if variant)


def find_user_by_phone(db: Session, phone: str) -> User | None:
    return (
        db.query(User)
        .filter(User.phone.in_(phone_variants(phone)))
        .order_by(User.id)
        .first()
    )


def find_user_by_email(db: Session, email: str) -> User | None:
    """Email без учёта регистра: Telegram на телефоне любит заглавную букву."""
    return (
        db.query(User)
        .filter(func.lower(User.email) == email.strip().lower())
        .order_by(User.id)
        .first()
    )


ALGORITHM = "HS256"
# Покупатель не должен перелогиниваться каждый час: по умолчанию 7 дней
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7))
)

password_hash = PasswordHash.recommended()

security = HTTPBearer()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password
    )


def create_access_token(
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None
) -> str:
    to_encode = {
        "user_id": user_id,
        "role": role
    }

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("user_id")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        ) from None

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    # Удалённый (обезличенный) аккаунт: ни телефона, ни почты — старый токен не действует
    if user is None or (user.phone is None and user.email is None):
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user


def require_role(required_role: str):
    def role_checker(
        current_user: User = Depends(get_current_user)
    ):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=403,
                detail="Access forbidden"
            )

        return current_user

    return role_checker


def require_customer(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "CUSTOMER":
        raise HTTPException(
            status_code=403,
            detail="Customer access required"
        )

    return current_user


def require_admin(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user


def require_owner(
    current_user: User = Depends(require_admin)
):
    if current_user.is_owner != 1:
        raise HTTPException(
            status_code=403,
            detail="Только владелец магазина может управлять администраторами"
        )

    return current_user


def find_user_by_login(db: Session, login: str) -> User | None:
    """Поиск по email (если есть «@») или по телефону."""
    login = login.strip()
    if "@" in login:
        return find_user_by_email(db, login)
    return find_user_by_phone(db, login)

