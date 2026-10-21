import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/wood_commerce"
)

# Пул: 5 постоянных соединений + 10 на пике (PostgreSQL на сервере — max 30,
# ещё бот и мониторинг). Ждать свободное соединение — не дольше 10 с: при
# перегрузке лучше быстро ответить ошибкой, чем копить очередь (нагрузочный
# тест — benchmarks/load/README.md). pre_ping — переподключиться, если базу
# перезапустили.
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    # Закрытая сессия больше не открывает соединений. Иначе, если клиент
    # оборвал запрос и сессию уже закрыли, поток обработчика молча брал новое
    # соединение — и его никто не возвращал: пул кончался, сайт зависал
    close_resets_only=False,
)

class Base(DeclarativeBase):
    """Базовый класс моделей (SQLAlchemy 2: типизированные Mapped-поля)."""


async def get_db():
    """Сессия на запрос.

    Зависимость асинхронная намеренно: закрытие сессии выполняется в цикле
    событий, а не ждёт свободный поток. С обычной (sync) зависимостью при
    перегрузке все потоки ждут соединение, а соединения держат сессии, которым
    не достаётся потока на close() — сайт зависал до перезапуска. Обработчики
    остаются синхронными и работают в пуле потоков, как раньше.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
