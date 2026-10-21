"""Назначение и снятие администраторов. Используется сайтом и ботом."""

from sqlalchemy.orm import Session

from ..auth import find_user_by_login
from ..models import TelegramAccountLink, User
from . import audit


class AdminServiceError(Exception):
    """Понятная пользователю ошибка (текст показывается как есть)."""


def list_admins(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == "ADMIN")
        .order_by(User.is_owner.desc(), User.id)
        .all()
    )


def has_telegram(db: Session, user: User) -> bool:
    return (
        db.query(TelegramAccountLink)
        .filter(TelegramAccountLink.user_id == user.id)
        .first()
        is not None
    )


def who(user: User) -> str:
    return user.phone or user.email or f"№{user.id}"


def add_admin(db: Session, login: str, actor: User | None = None) -> User:
    user = find_user_by_login(db, login)

    if user is None:
        raise AdminServiceError(
            "Пользователь не найден. Пусть сначала зарегистрируется на сайте "
            "по номеру телефона, затем добавь его ещё раз."
        )

    if user.role == "ADMIN":
        raise AdminServiceError("Этот пользователь уже администратор.")

    user.role = "ADMIN"
    audit.record(db, actor, "admin.added", "user", user.id, f"{who(user)} назначен администратором")
    db.commit()
    db.refresh(user)

    return user


def remove_admin(db: Session, user_id: int, actor: User) -> User:
    user = db.query(User).filter(User.id == user_id).first()

    if user is None or user.role != "ADMIN":
        raise AdminServiceError("Администратор не найден.")

    if user.is_owner == 1:
        raise AdminServiceError("Владельца нельзя лишить прав администратора.")

    if user.id == actor.id:
        raise AdminServiceError("Нельзя снять права с самого себя.")

    user.role = "CUSTOMER"
    audit.record(db, actor, "admin.removed", "user", user.id, f"{who(user)} больше не администратор")
    db.commit()
    db.refresh(user)

    return user
