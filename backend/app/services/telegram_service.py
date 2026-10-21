import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def telegram_api_url(token: str) -> str:
    """Адрес Bot API. TELEGRAM_API_URL — посредник, если api.telegram.org закрыт
    с сервера (например, Cloudflare Worker из deploy/telegram-relay-worker.js)."""
    base = os.getenv("TELEGRAM_API_URL", "").strip() or "https://api.telegram.org"
    return f"{base.rstrip('/')}/bot{token}"


def telegram_file_url(token: str, file_path: str) -> str:
    """Скачивание файла (фото товара), через того же посредника, что и API."""
    base = os.getenv("TELEGRAM_API_URL", "").strip() or "https://api.telegram.org"
    return f"{base.rstrip('/')}/file/bot{token}/{file_path}"


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

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(
            f"{telegram_api_url(token)}/sendMessage",
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
