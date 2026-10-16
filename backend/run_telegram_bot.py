import html
import logging
import os
import time

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import joinedload

from app.auth import verify_password
from app.database import SessionLocal
from app.models import User, Order, Product, OrderItem, TelegramAccountLink
from app.routers.orders import (
    STATUS_NAMES,
    build_order_keyboard,
    build_order_message,
    get_status_value,
)
from app.services.order_service import ALLOWED_TRANSITIONS, change_order_status

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")
API_URL = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""

user_states = {}
# Last bot screen per Telegram user: (chat_id, message_id).
screen_messages = {}
PAGE_SIZE = 5


def telegram_request(method: str, payload: dict) -> dict:
    response = requests.post(f"{API_URL}/{method}", json=payload, timeout=35)
    try:
        result = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError("Telegram API returned a non-JSON response")
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
        logger.exception("Не удалось обработать нажатие inline-кнопки")


def main_keyboard(role: str | None = None) -> dict:
    if role == "CUSTOMER":
        rows = [[{"text": "📦 Мои заказы"}], [{"text": "🔓 Выйти"}]]
    elif role == "ADMIN":
        rows = [[{"text": "📋 Все заказы"}], [{"text": "🔓 Выйти"}]]
    elif role == "DRIVER":
        rows = [[{"text": "🚚 Мои доставки"}], [{"text": "🔓 Выйти"}]]
    else:
        rows = [[{"text": "🔑 Войти"}]]
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


def get_link(db, telegram_user_id: int):
    return db.query(TelegramAccountLink).filter(
        TelegramAccountLink.telegram_user_id == telegram_user_id
    ).first()


def get_logged_user(db, telegram_user_id: int):
    link = get_link(db, telegram_user_id)
    if link is None:
        return None
    return db.query(User).filter(User.id == link.user_id).first()


def order_query(db):
    return db.query(Order).options(joinedload(Order.items).joinedload(OrderItem.product))


def show_screen(chat_id: int, telegram_user_id: int, text: str, keyboard=None):
    """Edit the previous bot screen where possible; otherwise send one and remove the old one."""
    old = screen_messages.get(telegram_user_id)
    # Telegram reply keyboards (the regular menu) cannot be attached to editMessageText.
    # Only try editing when the new markup is an inline keyboard or no markup at all.
    can_edit = keyboard is None or (
        isinstance(keyboard, dict) and isinstance(keyboard.get("inline_keyboard"), list)
    )
    if old and old[0] == chat_id and can_edit:
        try:
            edit_message(chat_id, old[1], text, keyboard)
            return old[1]
        except Exception as exc:
            logger.info("Не получилось отредактировать экран (%s); отправляю новый", exc)
    sent = send_message(chat_id, text, keyboard)
    new_id = sent["message_id"]
    screen_messages[telegram_user_id] = (chat_id, new_id)
    if old and old[0] == chat_id and old[1] != new_id:
        delete_message(chat_id, old[1])
    return new_id


def home_screen(chat_id: int, telegram_user_id: int):
    db = SessionLocal()
    try:
        user = get_logged_user(db, telegram_user_id)
        role = user.role if user else None
    finally:
        db.close()
    text = (
        "🌲 <b>Магазин пиломатериалов</b>\n\n"
        "Здесь можно просматривать заказы и получать уведомления "
        "об изменении их статуса.\n\nВыбери действие в меню ниже."
    )
    show_screen(chat_id, telegram_user_id, text, main_keyboard(role))


def login_prompt(chat_id: int, telegram_user_id: int):
    user_states[telegram_user_id] = {"step": "login", "chat_id": chat_id}
    show_screen(
        chat_id,
        telegram_user_id,
        "🔐 <b>Вход в личный кабинет</b>\n\n"
        "Отправь номер телефона или email, указанный при регистрации.\n"
        "Следующим сообщением бот попросит пароль.\n\n"
        "Для отмены отправь /cancel.",
        main_keyboard(),
    )


def handle_login_message(message: dict, state: dict) -> None:
    chat_id = message["chat"]["id"]
    telegram_user_id = message["from"]["id"]
    text = (message.get("text") or "").strip()

    if text in ("/cancel", "❌ Отмена"):
        user_states.pop(telegram_user_id, None)
        home_screen(chat_id, telegram_user_id)
        return

    if state["step"] == "login":
        if not text or len(text) > 255:
            show_screen(chat_id, telegram_user_id, "Введи корректный телефон или email.", main_keyboard())
            return
        state["login"] = text
        state["step"] = "password"
        show_screen(
            chat_id, telegram_user_id,
            "🔑 <b>Теперь отправь пароль</b>\n\n"
            "Сообщение с паролем будет удалено ботом, если Telegram разрешит.",
            main_keyboard(),
        )
        return

    password = text
    delete_message(chat_id, message["message_id"])
    db = SessionLocal()
    try:
        login = state["login"].strip()
        if "@" in login:
            user = db.query(User).filter(User.email == login).first()
        else:
            normalized_phone = "".join(ch for ch in login if ch.isdigit() or ch == "+")
            user = db.query(User).filter(User.phone == normalized_phone).first()

        if user is None or not verify_password(password, user.password_hash):
            user_states.pop(telegram_user_id, None)
            show_screen(
                chat_id, telegram_user_id,
                "❌ <b>Не удалось войти</b>\n\nПроверь телефон/email и пароль, затем попробуй снова.",
                main_keyboard(),
            )
            return

        if user.role == "ADMIN" and str(telegram_user_id) != ADMIN_ID:
            user_states.pop(telegram_user_id, None)
            show_screen(chat_id, telegram_user_id, "⛔ У этого Telegram нет доступа администратора.", main_keyboard())
            return

        by_user = db.query(TelegramAccountLink).filter(
            TelegramAccountLink.user_id == user.id
        ).first()
        by_telegram = get_link(db, telegram_user_id)
        if by_user and by_user.telegram_user_id != telegram_user_id:
            user_states.pop(telegram_user_id, None)
            show_screen(chat_id, telegram_user_id, "Этот аккаунт сайта уже связан с другим Telegram.", main_keyboard())
            return
        if by_telegram and by_telegram.user_id != user.id:
            user_states.pop(telegram_user_id, None)
            show_screen(chat_id, telegram_user_id, "Этот Telegram уже связан с другим аккаунтом сайта.", main_keyboard())
            return

        if by_user is None:
            db.add(TelegramAccountLink(
                user_id=user.id,
                telegram_user_id=telegram_user_id,
                telegram_chat_id=chat_id,
            ))
        else:
            by_user.telegram_chat_id = chat_id
        db.commit()
        role_names = {"CUSTOMER": "покупателя", "ADMIN": "администратора", "DRIVER": "водителя"}
        user_states.pop(telegram_user_id, None)
        show_screen(
            chat_id, telegram_user_id,
            "✅ <b>Вход выполнен!</b>\n\n"
            f"Ты вошёл как: {role_names.get(user.role, user.role)}.\n"
            "Аккаунт сайта связан с этим Telegram.",
            main_keyboard(user.role),
        )
    except Exception:
        db.rollback()
        logger.exception("Ошибка авторизации Telegram")
        user_states.pop(telegram_user_id, None)
        show_screen(chat_id, telegram_user_id, "⚠️ Техническая ошибка при входе. Попробуй позже.", main_keyboard())
    finally:
        db.close()


def customer_orders_keyboard(orders, page: int, total: int) -> dict:
    rows = []
    for order in orders:
        status = STATUS_NAMES.get(get_status_value(order.status), get_status_value(order.status))
        rows.append([{
            "text": f"📦 Заказ №{order.id} · {status}",
            "callback_data": f"customer:order:{order.id}",
        }])
    navigation = []
    if page > 0:
        navigation.append({"text": "◀️ Назад", "callback_data": f"customer:page:{page - 1}"})
    if (page + 1) * PAGE_SIZE < total:
        navigation.append({"text": "Вперёд ▶️", "callback_data": f"customer:page:{page + 1}"})
    if navigation:
        rows.append(navigation)
    rows.append([{"text": "🏠 Главное меню", "callback_data": "customer:home"}])
    return {"inline_keyboard": rows}


def show_customer_orders(chat_id: int, telegram_user_id: int, page: int = 0, message_id: int | None = None):
    db = SessionLocal()
    try:
        user = get_logged_user(db, telegram_user_id)
        if user is None or user.role != "CUSTOMER":
            show_screen(chat_id, telegram_user_id, "Сначала войди в аккаунт покупателя.", main_keyboard())
            return
        total = db.query(Order).filter(Order.user_id == user.id).count()
        if total == 0:
            text = "📦 <b>Мои заказы</b>\n\nУ тебя пока нет заказов."
            keyboard = {"inline_keyboard": [[{"text": "🏠 Главное меню", "callback_data": "customer:home"}]]}
        else:
            max_page = (total - 1) // PAGE_SIZE
            page = max(0, min(page, max_page))
            orders = order_query(db).filter(Order.user_id == user.id).order_by(
                Order.id.desc()
            ).offset(page * PAGE_SIZE).limit(PAGE_SIZE).all()
            text = (
                "📦 <b>Мои заказы</b>\n\n"
                f"Всего заказов: <b>{total}</b>\n"
                f"Страница: <b>{page + 1} из {max_page + 1}</b>\n\n"
                "Нажми на заказ, чтобы посмотреть подробности."
            )
            keyboard = customer_orders_keyboard(orders, page, total)
        # Callback buttons must edit the exact message that owns them.
        if message_id is not None:
            try:
                edit_message(chat_id, message_id, text, keyboard)
                screen_messages[telegram_user_id] = (chat_id, message_id)
                return
            except Exception:
                logger.info("Не удалось обновить список заказов", exc_info=True)
        show_screen(chat_id, telegram_user_id, text, keyboard)
    except Exception:
        logger.exception("Не удалось получить заказы клиента")
        show_screen(chat_id, telegram_user_id, "⚠️ Не удалось загрузить заказы. Проверь логи бота.")
    finally:
        db.close()


def show_customer_order(chat_id: int, telegram_user_id: int, order_id: int, message_id: int | None = None):
    db = SessionLocal()
    try:
        user = get_logged_user(db, telegram_user_id)
        if user is None or user.role != "CUSTOMER":
            show_screen(chat_id, telegram_user_id, "Сначала войди как покупатель.", main_keyboard())
            return
        order = order_query(db).filter(Order.id == order_id, Order.user_id == user.id).first()
        if order is None:
            show_screen(chat_id, telegram_user_id, "Заказ не найден или нет доступа к нему.", main_keyboard())
            return
        text = build_order_message(order, f"📦 Информация о заказе №{order.id}")
        keyboard = {"inline_keyboard": [
            [{"text": "◀️ К списку заказов", "callback_data": "customer:page:0"}],
            [{"text": "🏠 Главное меню", "callback_data": "customer:home"}],
        ]}
        if message_id is not None:
            try:
                edit_message(chat_id, message_id, text, keyboard)
                screen_messages[telegram_user_id] = (chat_id, message_id)
                return
            except Exception:
                logger.info("Не удалось открыть заказ редактированием", exc_info=True)
        show_screen(chat_id, telegram_user_id, text, keyboard)
    except Exception:
        logger.exception("Не удалось загрузить заказ №%s", order_id)
        show_screen(chat_id, telegram_user_id, "⚠️ Не удалось загрузить информацию о заказе.")
    finally:
        db.close()


def admin_orders_keyboard(orders, page: int, total: int) -> dict:
    rows = []
    for order in orders:
        status = STATUS_NAMES.get(get_status_value(order.status), get_status_value(order.status))
        rows.append([{
            "text": f"№{order.id} · {status}",
            "callback_data": f"admin:order:{order.id}",
        }])
    nav = []
    if page > 0:
        nav.append({"text": "◀️ Назад", "callback_data": f"admin:page:{page - 1}"})
    if (page + 1) * PAGE_SIZE < total:
        nav.append({"text": "Вперёд ▶️", "callback_data": f"admin:page:{page + 1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": "🏠 Главное меню", "callback_data": "admin:home"}])
    return {"inline_keyboard": rows}


def show_admin_orders(chat_id: int, telegram_user_id: int, page: int = 0, message_id: int | None = None):
    if str(telegram_user_id) != ADMIN_ID:
        show_screen(chat_id, telegram_user_id, "⛔ Нет доступа.", main_keyboard())
        return
    db = SessionLocal()
    try:
        user = get_logged_user(db, telegram_user_id)
        if user is None or user.role != "ADMIN":
            show_screen(chat_id, telegram_user_id, "Сначала войди как администратор.", main_keyboard())
            return
        total = db.query(Order).count()
        if total == 0:
            text = "📋 <b>Все заказы</b>\n\nЗаказов пока нет."
            keyboard = {"inline_keyboard": [[{"text": "🏠 Главное меню", "callback_data": "admin:home"}]]}
        else:
            max_page = (total - 1) // PAGE_SIZE
            page = max(0, min(page, max_page))
            orders = db.query(Order).order_by(Order.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE).all()
            text = (
                "📋 <b>Все заказы</b>\n\n"
                f"Всего: <b>{total}</b>\n"
                f"Страница: <b>{page + 1} из {max_page + 1}</b>\n\n"
                "Выбери заказ для просмотра и изменения статуса."
            )
            keyboard = admin_orders_keyboard(orders, page, total)
        if message_id is not None:
            try:
                edit_message(chat_id, message_id, text, keyboard)
                screen_messages[telegram_user_id] = (chat_id, message_id)
                return
            except Exception:
                logger.info("Не удалось обновить список заказов администратора", exc_info=True)
        show_screen(chat_id, telegram_user_id, text, keyboard)
    except Exception as exc:
        logger.exception("Не удалось загрузить заказы администратора: %s", exc)
        show_screen(chat_id, telegram_user_id, "⚠️ Не удалось загрузить заказы. Посмотри ошибку в терминале, где запущен бот.")
    finally:
        db.close()


def restore_order_stock(db, order: Order) -> None:
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).with_for_update().first()
        if product is not None:
            product.stock_quantity += item.quantity




def safe_order_keyboard(order_id: int, current_status: str) -> dict:
    """Build inline status buttons even if the router helper returns None."""
    keyboard = build_order_keyboard(order_id, current_status)
    if isinstance(keyboard, dict) and isinstance(keyboard.get("inline_keyboard"), list):
        rows = keyboard["inline_keyboard"]
    else:
        rows = []
        for next_status in sorted(ALLOWED_TRANSITIONS.get(current_status, set())):
            label = STATUS_NAMES.get(next_status, next_status)
            rows.append([{"text": f"➡️ {label}", "callback_data": f"order:{order_id}:{next_status}"}])
    return {"inline_keyboard": rows}

def show_admin_order(chat_id: int, telegram_user_id: int, order_id: int, message_id: int | None = None):
    if str(telegram_user_id) != ADMIN_ID:
        show_screen(chat_id, telegram_user_id, "⛔ Нет доступа.", main_keyboard())
        return
    db = SessionLocal()
    try:
        user = get_logged_user(db, telegram_user_id)
        if user is None or user.role != "ADMIN":
            show_screen(chat_id, telegram_user_id, "Сначала войди как администратор.", main_keyboard())
            return
        order = order_query(db).filter(Order.id == order_id).first()
        if order is None:
            show_screen(chat_id, telegram_user_id, "Заказ не найден.")
            return
        text = build_order_message(order, f"📦 Заказ №{order.id}")
        keyboard = safe_order_keyboard(order.id, get_status_value(order.status))
        rows = keyboard["inline_keyboard"]
        rows.append([{"text": "◀️ К списку заказов", "callback_data": "admin:page:0"}])
        rows.append([{"text": "🏠 Главное меню", "callback_data": "admin:home"}])
        keyboard = {"inline_keyboard": rows}
        if message_id is not None:
            try:
                edit_message(chat_id, message_id, text, keyboard)
                screen_messages[telegram_user_id] = (chat_id, message_id)
                return
            except Exception:
                logger.info("Не удалось открыть карточку заказа редактированием", exc_info=True)
        show_screen(chat_id, telegram_user_id, text, keyboard)
    except Exception:
        logger.exception("Не удалось открыть заказ администратора")
        show_screen(chat_id, telegram_user_id, "⚠️ Не удалось открыть заказ.")
    finally:
        db.close()


def handle_admin_callback(callback: dict, data: str) -> None:
    callback_id = callback["id"]
    sender = callback.get("from", {})
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    if str(sender.get("id")) != ADMIN_ID:
        answer_callback(callback_id, "⛔ Нет доступа.", alert=True)
        return
    if chat.get("type") != "private":
        answer_callback(callback_id, "Открой личный чат с ботом.", alert=True)
        return

    parts = data.split(":")
    if len(parts) == 3 and parts[0] == "admin":
        action, value = parts[1], parts[2]
        answer_callback(callback_id)
        if action == "page":
            try:
                show_admin_orders(chat["id"], sender["id"], int(value), message.get("message_id"))
            except ValueError:
                answer_callback(callback_id, "Некорректная страница.", alert=True)
            return
        if action == "order":
            try:
                show_admin_order(chat["id"], sender["id"], int(value), message.get("message_id"))
            except ValueError:
                answer_callback(callback_id, "Некорректный номер заказа.", alert=True)
            return
        if action == "status":
            # Legacy status buttons use order:<id>:<status>, handled below.
            return
    if len(parts) != 3 or parts[0] != "order":
        answer_callback(callback_id, "Неизвестная команда.", alert=True)
        return

    db = SessionLocal()
    try:
        user = get_logged_user(db, sender["id"])
        if user is None or user.role != "ADMIN":
            answer_callback(callback_id, "Сначала войди как администратор.", alert=True)
            return
        try:
            order_id = int(parts[1])
        except ValueError:
            answer_callback(callback_id, "Некорректный номер заказа.", alert=True)
            return
        new_status = parts[2]
        valid_statuses = {status for transitions in ALLOWED_TRANSITIONS.values() for status in transitions}
        if new_status not in valid_statuses:
            answer_callback(callback_id, "Неизвестный статус.", alert=True)
            return
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if order is None:
            answer_callback(callback_id, "Заказ не найден.", alert=True)
            return
        previous_status = get_status_value(order.status)
        if new_status not in ALLOWED_TRANSITIONS.get(previous_status, set()):
            answer_callback(callback_id, "Этот переход статуса недоступен.", alert=True)
            return
        change_order_status(order, new_status, db, user.id)
        if new_status == "CANCELLED":
            restore_order_stock(db, order)
        db.commit()
        db.refresh(order)
        status_name = STATUS_NAMES.get(new_status, new_status)
        updated_text = build_order_message(order, f"🔔 Статус заказа №{order.id}: {status_name}")
        keyboard = safe_order_keyboard(order.id, get_status_value(order.status))
        rows = keyboard["inline_keyboard"]
        rows.append([{"text": "◀️ К списку заказов", "callback_data": "admin:page:0"}])
        rows.append([{"text": "🏠 Главное меню", "callback_data": "admin:home"}])
        try:
            edit_message(chat["id"], message["message_id"], updated_text, {"inline_keyboard": rows})
        except Exception:
            logger.exception("Статус изменён, но экран заказа не обновился")

        link = db.query(TelegramAccountLink).filter(TelegramAccountLink.user_id == order.user_id).first()
        if link:
            try:
                send_message(
                    link.telegram_chat_id,
                    f"🔔 <b>Обновление заказа №{order.id}</b>\n\n"
                    f"Новый статус: <b>{html.escape(status_name)}</b>.",
                )
            except Exception:
                logger.exception("Не удалось отправить уведомление покупателю")
        answer_callback(callback_id, f"Заказ №{order_id}: {status_name}")
    except Exception:
        db.rollback()
        logger.exception("Ошибка обработки заказа")
        answer_callback(callback_id, "Не удалось обновить заказ. Проверь логи.", alert=True)
    finally:
        db.close()


def handle_callback(callback: dict) -> None:
    callback_id = callback["id"]
    data = callback.get("data", "")
    sender = callback.get("from", {})
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    if not chat or chat.get("type") != "private":
        answer_callback(callback_id, "Открой личный чат с ботом.", alert=True)
        return
    telegram_user_id = sender.get("id")
    chat_id = chat.get("id")
    message_id = message.get("message_id")

    if data.startswith("order:"):
        handle_admin_callback(callback, data)
        return

    if data.startswith("admin:"):
        parts = data.split(":")
        if len(parts) == 2 and parts[1] == "home":
            answer_callback(callback_id)
            home_screen(chat_id, telegram_user_id)
        else:
            handle_admin_callback(callback, data)
        return

    if not data.startswith("customer:"):
        answer_callback(callback_id, "Неизвестная команда.", alert=True)
        return

    db = SessionLocal()
    try:
        user = get_logged_user(db, telegram_user_id)
    finally:
        db.close()
    if user is None or user.role != "CUSTOMER":
        answer_callback(callback_id, "Сначала войди как покупатель.", alert=True)
        return

    parts = data.split(":")
    if len(parts) == 3 and parts[1] == "page":
        try:
            page = int(parts[2])
        except ValueError:
            answer_callback(callback_id, "Некорректная страница.", alert=True)
            return
        answer_callback(callback_id)
        show_customer_orders(chat_id, telegram_user_id, page, message_id)
        return
    if len(parts) == 3 and parts[1] == "order":
        try:
            order_id = int(parts[2])
        except ValueError:
            answer_callback(callback_id, "Некорректный номер заказа.", alert=True)
            return
        answer_callback(callback_id)
        show_customer_order(chat_id, telegram_user_id, order_id, message_id)
        return
    if data == "customer:home":
        answer_callback(callback_id)
        home_screen(chat_id, telegram_user_id)
        return
    answer_callback(callback_id, "Неизвестная команда.", alert=True)


def handle_message(message: dict) -> None:
    chat = message.get("chat", {})
    sender = message.get("from", {})
    chat_id = chat.get("id")
    telegram_user_id = sender.get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not telegram_user_id or chat.get("type") != "private":
        return

    if text == "/cancel":
        user_states.pop(telegram_user_id, None)
        home_screen(chat_id, telegram_user_id)
        return

    state = user_states.get(telegram_user_id)
    if state:
        handle_login_message(message, state)
        return

    if text in ("/start", "Начать"):
        home_screen(chat_id, telegram_user_id)
        return
    if text in ("🔑 Войти", "👤 Войти как клиент", "🔐 Войти как администратор"):
        login_prompt(chat_id, telegram_user_id)
        return
    if text == "📦 Мои заказы":
        show_customer_orders(chat_id, telegram_user_id)
        return
    if text in ("📋 Все заказы", "📦 Последние заказы"):
        show_admin_orders(chat_id, telegram_user_id)
        return
    if text == "🚚 Мои доставки":
        show_screen(chat_id, telegram_user_id, "🚚 Раздел доставок пока не реализован.", main_keyboard("DRIVER"))
        return
    if text == "🔓 Выйти":
        db = SessionLocal()
        try:
            link = get_link(db, telegram_user_id)
            if link:
                db.delete(link)
                db.commit()
        finally:
            db.close()
        user_states.pop(telegram_user_id, None)
        show_screen(chat_id, telegram_user_id, "Ты вышел из аккаунта.", main_keyboard())
        return
    # Remove ordinary text after handling login; never create an endless trail of bot replies.
    if text and not text.startswith("/"):
        delete_message(chat_id, message["message_id"])


def main() -> None:
    if not TOKEN or not CHAT_ID or not ADMIN_ID:
        raise RuntimeError(
            "Укажи TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID и TELEGRAM_ADMIN_ID в backend/.env"
        )

    # This bot uses long polling. A webhook left by another deployment prevents getUpdates.
    telegram_request("deleteWebhook", {"drop_pending_updates": False})
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


if __name__ == "__main__":
    main()
