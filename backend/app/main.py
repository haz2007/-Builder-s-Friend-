from datetime import UTC, datetime, timedelta

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db
from .routers.admin import router as admin_router
from .routers.admins import router as admins_router
from .routers.auth import router as auth_router
from .routers.categories import router as categories_router
from .routers.notifications import router as notifications_router
from .routers.orders import router as orders_router
from .routers.products import UPLOAD_DIR
from .routers.products import router as products_router
from .routers.users import router as users_router

OPENAPI_TAGS = [
    {"name": "Authentication", "description": "Регистрация по телефону и вход (JWT, 7 дней)"},
    {"name": "Products", "description": "Каталог, варианты продажи (штука, куб, пачка), размеры досок, фото"},
    {"name": "Categories", "description": "Разделы и подкатегории (два уровня)"},
    {"name": "orders", "description": "Заказы: оформление, отмена, смена статуса, история"},
    {"name": "Notifications", "description": "Уведомления покупателя в личном кабинете"},
    {"name": "Admin", "description": "Аналитика и сводка для администраторов"},
    {"name": "Admins", "description": "Управление администраторами (только владелец)"},
    {"name": "Users", "description": "Пользователи и роли"},
]

app = FastAPI(
    title="Друг Строителя API",
    description=(
        "API интернет-магазина пиломатериалов и крепежа. "
        "Бизнес-правила — docs/business-rules.md, диаграммы — docs/diagrams.md."
    ),
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,
)

# Создаём папку для фотографий товаров
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Раздаём всю папку uploads, чтобы URL /uploads/products/... работал
UPLOAD_ROOT = UPLOAD_DIR.parent

app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_ROOT)),
    name="uploads",
)

app.include_router(products_router)
app.include_router(categories_router)
app.include_router(orders_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(notifications_router)
app.include_router(admins_router)


@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    """Жив ли сервис: отвечает база и не застряли ли сообщения в Telegram.

    Его опрашивают Docker (healthcheck), scripts/healthcheck.sh и внешний
    монитор. Нет связи с базой — 503.
    """
    try:
        db.execute(text("SELECT 1"))
        stuck = db.execute(text(
            "SELECT count(*) FILTER (WHERE status = 'pending' AND created_at < :limit) AS stuck, "
            "count(*) FILTER (WHERE status = 'failed') AS failed FROM telegram_outbox"
        ), {"limit": datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)}).one()
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "error", "database": "unavailable"})
    return {
        "status": "ok",
        "service": "wood-commerce-api",
        "database": "ok",
        # Сообщения, которые не уходят дольше 10 минут, и окончательно не отправленные
        "outbox_stuck": stuck.stuck,
        "outbox_failed": stuck.failed,
    }
