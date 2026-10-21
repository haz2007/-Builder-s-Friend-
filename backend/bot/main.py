"""Запуск: long polling с повторными попытками, если Telegram недоступен."""

import threading
import time

from app.services.order_notifications import deliver_pending

from .config import TOKEN, logger
from .handlers import handle_callback, handle_message
from .screens import setup_bot_profile
from .telegram import telegram_request

OUTBOX_INTERVAL = 3  # секунды между проходами по очереди сообщений


def outbox_worker() -> None:
    """Досылает сообщения из outbox: если API упал после сохранения заказа
    или Telegram был недоступен — сообщения уйдут отсюда, с повторами."""
    while True:
        try:
            deliver_pending()
        except Exception:
            logger.exception("Ошибка очереди сообщений")
        time.sleep(OUTBOX_INTERVAL)


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
    threading.Thread(target=outbox_worker, name="outbox", daemon=True).start()
    logger.info("Telegram-бот запускается; polling включён, очередь сообщений — каждые %s с.", OUTBOX_INTERVAL)
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
