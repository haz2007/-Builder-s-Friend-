"""Настройки бота, общие константы и состояние диалогов."""

import logging
import os

from dotenv import load_dotenv

from app.services.telegram_service import telegram_api_url

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
# requests/urllib3 не должны писать URL с токеном в лог
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = telegram_api_url(TOKEN) if TOKEN else ""

PAGE_SIZE = 5
LOW_STOCK_LIMIT = 10

# Ожидаемый ввод пользователя: вход (логин → пароль) или добавление админа
user_states: dict[int, dict] = {}
# Последний «экран» бота у пользователя: (chat_id, message_id)
screen_messages: dict[int, tuple[int, int]] = {}

ORDER_FILTERS = {
    "new": ("🆕 Новые", ["NEW"]),
    "work": (
        "🔄 В работе",
        ["CONFIRMED", "PREPARING", "READY_FOR_DELIVERY", "ON_THE_WAY"],
    ),
    "done": ("✅ Завершённые", ["DELIVERED", "CANCELLED"]),
    "all": ("📋 Все", None),
}

ROLE_NAMES = {
    "CUSTOMER": "покупатель",
    "ADMIN": "администратор",
}
