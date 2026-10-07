from fastapi import FastAPI

from .database import Base, engine
from .models import Category, Product, Delivery
from .routers.products import router as products_router
from .routers.categories import router as categories_router
from .routers.orders import router as orders_router
from .routers.auth import router as auth_router
from .routers.deliveries import router as deliveries_router
from .routers.users import router as users_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Wood Commerce API",
    description="API for construction materials and lumber commerce platform",
    version="1.0.0",
)


app.include_router(products_router)
app.include_router(categories_router)
app.include_router(orders_router)
app.include_router(auth_router)
app.include_router(deliveries_router)
app.include_router(users_router)


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "ok",
        "service": "wood-commerce-api"
    }