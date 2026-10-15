import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def send_telegram_message(
    message: str,
    reply_markup: dict | None = None,
) -> bool:
    """
    Отправляет сообщение в Telegram.
    При необходимости добавляет inline-кнопки.
    Возвращает True при успехе и False при ошибке.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning(
            "Telegram не настроен: проверь TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID."
        )
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=5,
        )
        response.raise_for_status()

        result = response.json()

        if not result.get("ok"):
            logger.error("Telegram не подтвердил отправку сообщения.")
            return False

        return True

    except requests.RequestException:
        logger.exception("Не удалось отправить сообщение в Telegram.")
        return False
    except ValueError:
        logger.exception("Telegram вернул некорректный ответ.")
        return False
