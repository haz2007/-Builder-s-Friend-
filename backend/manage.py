"""Служебные команды.

Создать таблицы в пустой базе (первые миграции проекта не создают
таблицы с нуля, поэтому для новой базы — так):
    .venv/bin/python manage.py init-db

Назначить владельца магазина (он сможет добавлять других админов):
    .venv/bin/python manage.py set-owner owner@example.com
    .venv/bin/python manage.py set-owner +79991234567
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app import models  # noqa: F401 — регистрирует модели в Base.metadata
from app.auth import find_user_by_login
from app.database import Base, SessionLocal, engine


def init_db() -> None:
    """Таблицы по моделям + отметка, что все миграции уже применены."""
    Base.metadata.create_all(engine)
    command.stamp(Config(str(Path(__file__).with_name("alembic.ini"))), "head")
    print("Готово: таблицы созданы, база на последней миграции")


def set_owner(login: str) -> None:
    db = SessionLocal()
    try:
        user = find_user_by_login(db, login)
        if user is None:
            sys.exit(f"Пользователь «{login}» не найден")

        user.role = "ADMIN"
        user.is_owner = 1
        db.commit()
        print(f"Готово: пользователь №{user.id} теперь владелец магазина")
    finally:
        db.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["init-db"]:
        init_db()
    elif len(sys.argv) == 3 and sys.argv[1] == "set-owner":
        set_owner(sys.argv[2])
    else:
        sys.exit(__doc__)
