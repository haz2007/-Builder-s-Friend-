from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin, require_owner
from ..database import get_db
from ..models import User
from ..schemas import TemporaryPasswordResponse, UserResponse
from ..services import audit, password_reset

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


@router.patch("/{user_id}/role", response_model=UserResponse)
def change_user_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    # Назначать роли (в том числе ADMIN) может только владелец
    current_user: User = Depends(require_owner)
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
        "ADMIN"
    }

    if role not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail="Invalid role"
        )

    if user.is_owner == 1 and role != "ADMIN":
        raise HTTPException(
            status_code=400,
            detail="Владельца нельзя лишить прав администратора"
        )

    old_role = user.role
    user.role = role
    if old_role != role:
        audit.record(db, current_user, "user.role", "user", user.id,
                     f"{user.phone or user.email or f'№{user.id}'}: роль {old_role} → {role}")

    db.commit()
    db.refresh(user)

    return user


@router.post("/{user_id}/reset-password", response_model=TemporaryPasswordResponse)
def reset_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Временный пароль покупателю, у которого не подключён Telegram-бот:
    админ диктует его по телефону, покупатель потом меняет."""
    try:
        user, password = password_reset.reset_by_admin(db, user_id, current_user)
    except password_reset.PasswordResetError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"user_id": user.id, "phone": user.phone, "temporary_password": password}

