"""База для E2E-тестов (frontend/e2e): схема, пробные товары и тестовый админ.

Запускается из playwright.config.ts перед стартом бэкенда. Только для
отдельной тестовой базы — DATABASE_URL обязан указывать на *_e2e.
Повторный запуск безопасен.
"""

import os
import sys

from manage import migrate
from seed_demo import seed

from app.auth import hash_password
from app.database import DATABASE_URL, SessionLocal
from app.models import User

# Тестовые данные, не настоящий аккаунт; те же значения в frontend/e2e/shop.spec.ts
ADMIN_PHONE = "+79990000001"
ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "e2e-admin-pass")


def main() -> None:
    if not DATABASE_URL.rsplit("/", 1)[-1].endswith("_e2e"):
        sys.exit(f"seed_e2e: нужна отдельная база *_e2e, а не {DATABASE_URL.rsplit('/', 1)[-1]}")
    migrate()
    seed()
    db = SessionLocal()
    try:
        if db.query(User).filter(User.phone == ADMIN_PHONE).first() is None:
            db.add(User(phone=ADMIN_PHONE, password_hash=hash_password(ADMIN_PASSWORD), role="ADMIN"))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
