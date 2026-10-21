
import re
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token,
    find_user_by_email,
    find_user_by_phone,
    get_current_user,
    hash_password,
    verify_password,
)
from ..database import get_db
from ..models import User
from ..rate_limit import login_limiter, register_limiter, reset_confirm_limiter, reset_request_limiter
from ..schemas import (
    LoginRequest,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
    UserRegister,
    UserResponse,
)
from ..services import password_reset

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


@router.post(
    "/register",
    response_model=UserResponse,
    dependencies=[Depends(register_limiter)],
)
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
        privacy_accepted_at=datetime.now(UTC),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(login_limiter)],
)
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
        # Выше проверено: указан ровно один идентификатор — здесь это email
        user = find_user_by_email(db, login_data.email or "")

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


@router.post("/change-password", dependencies=[Depends(login_limiter)])
def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Смена пароля из личного кабинета — например, после временного пароля от админа."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Текущий пароль указан неверно.")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail="Новый пароль совпадает с текущим.")
    user = db.get(User, current_user.id)
    assert user is not None
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"detail": "Пароль изменён."}


RESET_SENT = (
    "Если номер зарегистрирован и подключён к Telegram-боту магазина, код уже там. "
    "Если бот не подключён — позвоните в магазин, и вам сбросят пароль."
)


@router.post(
    "/password-reset/request",
    dependencies=[Depends(reset_request_limiter)],
)
def request_password_reset(
    data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Код для смены пароля приходит в Telegram-бота. Ответ один и тот же,
    есть такой номер или нет, — чтобы нельзя было перебирать номера."""
    message = password_reset.request_code(db, normalize_phone(data.phone))
    if message is not None:
        background_tasks.add_task(password_reset.send_code, *message)
    return {"detail": RESET_SENT}


@router.post(
    "/password-reset/confirm",
    response_model=TokenResponse,
    dependencies=[Depends(reset_confirm_limiter)],
)
def confirm_password_reset(
    data: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Новый пароль по коду из Telegram; сразу выполняется вход."""
    try:
        user = password_reset.confirm_code(db, normalize_phone(data.phone), data.code, data.new_password)
    except password_reset.PasswordResetError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"access_token": create_access_token(user_id=user.id, role=user.role), "token_type": "bearer"}

