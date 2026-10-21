"""Запросы к Telegram Bot API и «экран» бота: одно сообщение, которое обновляется."""


import requests

from app.services.telegram_service import telegram_proxies

from .config import API_URL, logger, screen_messages


def telegram_request(method: str, payload: dict) -> dict:
    response = requests.post(
        f"{API_URL}/{method}", json=payload, timeout=35, proxies=telegram_proxies()
    )
    try:
        result = response.json()
    except ValueError as error:
        response.raise_for_status()
        raise RuntimeError("Telegram API returned a non-JSON response") from error
    if response.status_code >= 400 or not result.get("ok"):
        description = result.get("description", response.reason)
        raise RuntimeError(f"Telegram API error in {method}: {description}")
    return result["result"]


def send_message(chat_id: int, text: str, keyboard=None) -> dict:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard is not None:
        payload["reply_markup"] = keyboard
    return telegram_request("sendMessage", payload)


def edit_message(chat_id: int, message_id: int, text: str, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if keyboard is not None:
        payload["reply_markup"] = keyboard
    return telegram_request("editMessageText", payload)


def delete_message(chat_id: int, message_id: int) -> None:
    try:
        telegram_request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    except Exception:
        logger.debug("Не удалось удалить сообщение %s", message_id, exc_info=True)


def answer_callback(callback_id: str, text: str = "", alert=False) -> None:
    try:
        telegram_request(
            "answerCallbackQuery",
            {"callback_query_id": callback_id, "text": text, "show_alert": alert},
        )
    except Exception:
        logger.exception("Не удалось ответить на нажатие кнопки")


def show_screen(
    chat_id: int,
    telegram_user_id: int,
    text: str,
    keyboard=None,
    message_id: int | None = None,
):
    """Редактирует текущий экран, если можно, иначе отправляет новый.

    Обычное меню (reply keyboard) нельзя прикрепить при редактировании,
    поэтому такие экраны всегда отправляются новым сообщением.
    """
    is_inline = keyboard is None or "inline_keyboard" in keyboard
    target = message_id
    if target is None:
        old = screen_messages.get(telegram_user_id)
        if old and old[0] == chat_id:
            target = old[1]

    if target is not None and is_inline:
        try:
            edit_message(chat_id, target, text, keyboard)
            screen_messages[telegram_user_id] = (chat_id, target)
            return target
        except Exception as exc:
            if "message is not modified" in str(exc):
                return target
            logger.info("Не получилось отредактировать экран (%s); отправляю новый", exc)

    sent = send_message(chat_id, text, keyboard)
    new_id = sent["message_id"]
    old = screen_messages.get(telegram_user_id)
    screen_messages[telegram_user_id] = (chat_id, new_id)
    if old and old[0] == chat_id and old[1] != new_id:
        delete_message(chat_id, old[1])
    return new_id


def inline(*rows) -> dict:
    return {"inline_keyboard": [list(row) for row in rows if row]}


def button(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


HOME_ROW = [button("🏠 Главное меню", "home")]
