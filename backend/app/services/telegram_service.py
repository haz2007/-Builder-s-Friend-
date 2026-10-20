import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def telegram_proxies() -> dict | None:
    """TELEGRAM_PROXY=socks5://user:pass@host:port — если Telegram недоступен напрямую."""
    proxy = os.getenv("TELEGRAM_PROXY")
    return {"https": proxy, "http": proxy} if proxy else None


def send_telegram_message(
    chat_id: int | str,
    message: str,
    reply_markup: dict | None = None,
) -> bool:
    """Отправляет сообщение в конкретный чат Telegram.

    Возвращает True при успехе и False при ошибке или если бот не настроен.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.debug("Telegram не настроен: нет TELEGRAM_BOT_TOKEN.")
        return False

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10,
            proxies=telegram_proxies(),
        )
        result = response.json()

        if not result.get("ok"):
            logger.warning(
                "Telegram не доставил сообщение в чат %s: %s",
                chat_id,
                result.get("description"),
            )
            return False

        return True

    except requests.RequestException:
        logger.exception("Не удалось отправить сообщение в Telegram.")
        return False
    except ValueError:
        logger.exception("Telegram вернул некорректный ответ.")
        return False
