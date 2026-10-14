from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers.products import router as products_router, UPLOAD_DIR
from .routers.categories import router as categories_router
from .routers.orders import router as orders_router
from .routers.auth import router as auth_router
from .routers.deliveries import router as deliveries_router
from .routers.users import router as users_router
from .routers.admin import router as admin_router
from .routers.notifications import router as notifications_router


app = FastAPI(
    title="Wood Commerce API",
    description="API for construction materials and lumber commerce platform",
    version="1.0.0",
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
app.include_router(deliveries_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(notifications_router)


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "service": "wood-commerce-api"}