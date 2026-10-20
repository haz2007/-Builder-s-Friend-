import os

# Тесты должны работать только с тестовой базой
os.environ["DATABASE_URL"] = (
    "postgresql://postgres:postgres@localhost:5110/wood_commerce_test"
)

# Тесты никогда не пишут в настоящий Telegram: пустые значения
# load_dotenv() не перезаписывает, поэтому токен из backend/.env не подхватится
os.environ["TELEGRAM_BOT_TOKEN"] = ""

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.rate_limit import reset_all as reset_rate_limits


@pytest.fixture(autouse=True)
def clean_rate_limits():
    # Все запросы TestClient идут с одного «IP» — каждый тест начинает с нуля
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(reset_database):
    return TestClient(app)
