"""Запуск: long polling с повторными попытками, если Telegram недоступен."""

import time

from .config import TOKEN, logger
from .handlers import handle_callback, handle_message
from .screens import setup_bot_profile
from .telegram import telegram_request


def main() -> None:
    if not TOKEN:
        raise RuntimeError("Укажи TELEGRAM_BOT_TOKEN в backend/.env")

    # Бот работает через long polling; webhook от другого запуска мешает getUpdates
    # Сеть до Telegram бывает нестабильной: при старте не падаем, а ждём и пробуем снова
    delay = 3
    while True:
        try:
            telegram_request("deleteWebhook", {"drop_pending_updates": False})
            break
        except KeyboardInterrupt:
            return
        except Exception as error:
            logger.warning("Telegram недоступен при запуске (%s), повтор через %s с", error, delay)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    setup_bot_profile()
    logger.info("Telegram-бот запускается; polling включён.")
    offset = None
    while True:
        try:
            payload = {"timeout": 25, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                payload["offset"] = offset
            updates = telegram_request("getUpdates", payload)
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    if update.get("message"):
                        handle_message(update["message"])
                    elif update.get("callback_query"):
                        handle_callback(update["callback_query"])
                except Exception:
                    logger.exception("Ошибка обработки update_id=%s", update.get("update_id"))
        except KeyboardInterrupt:
            logger.info("Telegram-бот остановлен.")
            break
        except Exception:
            logger.exception("Ошибка опроса Telegram API")
            time.sleep(3)
