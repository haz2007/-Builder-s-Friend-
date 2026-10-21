"""Служебные команды.

Создать таблицы в пустой базе (первые миграции проекта не создают
таблицы с нуля, поэтому для новой базы — так):
    .venv/bin/python manage.py init-db

Привести базу в актуальное состояние (для Docker: новая база — init-db,
существующая — alembic upgrade head):
    .venv/bin/python manage.py migrate

Выгрузить спецификацию API в docs/api/openapi.json:
    .venv/bin/python manage.py export-openapi

Назначить владельца магазина (он сможет добавлять других админов):
    .venv/bin/python manage.py set-owner +79991234567
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app import models  # noqa: F401 — регистрирует модели в Base.metadata
from app.auth import find_user_by_phone
from app.database import Base, SessionLocal, engine


def init_db() -> None:
    """Таблицы по моделям + отметка, что все миграции уже применены."""
    Base.metadata.create_all(engine)
    command.stamp(Config(str(Path(__file__).with_name("alembic.ini"))), "head")
    print("Готово: таблицы созданы, база на последней миграции")


def migrate() -> None:
    from sqlalchemy import inspect

    if "alembic_version" not in inspect(engine).get_table_names():
        init_db()
        return
    command.upgrade(Config(str(Path(__file__).with_name("alembic.ini"))), "head")
    print("Готово: миграции применены")


OPENAPI_PATH = Path(__file__).resolve().parent.parent / "docs" / "api" / "openapi.json"


def openapi_json() -> str:
    import json

    from app.main import app

    return json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"


def export_openapi() -> None:
    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(openapi_json(), encoding="utf-8")
    print(f"Готово: {OPENAPI_PATH}")


def set_owner(login: str) -> None:
    db = SessionLocal()
    try:
        user = find_user_by_phone(db, login)
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
    elif sys.argv[1:] == ["migrate"]:
        migrate()
    elif sys.argv[1:] == ["export-openapi"]:
        export_openapi()
    elif len(sys.argv) == 3 and sys.argv[1] == "set-owner":
        set_owner(sys.argv[2])
    else:
        sys.exit(__doc__)
