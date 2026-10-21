"""Обработчики Telegram-бота (пакет bot/) без настоящего Telegram:
запросы к Bot API подменяются записью того, что бот отправил бы."""

import pytest

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Category, Order, OrderStatusHistory, Product, TelegramAccountLink, User
from bot import config, handlers, telegram

ADMIN_TG = 9001
CUSTOMER_TG = 9002


@pytest.fixture
def sent(monkeypatch, reset_database):
    calls = []

    def fake_request(method, payload):
        calls.append((method, payload))
        return {"message_id": 1000 + len(calls)}

    monkeypatch.setattr(telegram, "telegram_request", fake_request)
    config.user_states.clear()
    config.screen_messages.clear()
    yield calls
    config.user_states.clear()
    config.screen_messages.clear()


def message(text, telegram_id=CUSTOMER_TG):
    return {
        "message_id": 1,
        "chat": {"id": telegram_id, "type": "private"},
        "from": {"id": telegram_id},
        "text": text,
    }


def press(data, telegram_id):
    return {
        "id": "cb",
        "data": data,
        "from": {"id": telegram_id},
        "message": {"message_id": 1, "chat": {"id": telegram_id, "type": "private"}},
    }


def texts(calls):
    return [payload["text"] for method, payload in calls if "text" in payload and method != "answerCallbackQuery"]


def make_user(role, telegram_id=None, **fields):
    db = SessionLocal()
    user = User(password_hash=hash_password("secret-pass"), role=role, **fields)
    db.add(user)
    db.flush()
    if telegram_id:
        db.add(TelegramAccountLink(user_id=user.id, telegram_user_id=telegram_id, telegram_chat_id=telegram_id))
    db.commit()
    user_id = user.id
    db.close()
    return user_id


def make_order(user_id):
    db = SessionLocal()
    category = Category(name="Доска")
    db.add(category)
    db.flush()
    product = Product(name="Доска", price=600, stock_quantity=100, unit="шт", category_id=category.id, is_active=1)
    db.add(product)
    order = Order(customer_name="Сергей", delivery_address="Химки", status="NEW", total_price=600, user_id=user_id)
    db.add(order)
    db.flush()
    db.add(OrderStatusHistory(order_id=order.id, status="NEW", changed_by_id=user_id))
    db.commit()
    order_id = order.id
    db.close()
    return order_id


def test_guest_start_shows_login_menu(sent):
    handlers.handle_message(message("/start"))

    keyboard = [payload for method, payload in sent if "reply_markup" in payload][0]["reply_markup"]
    buttons = [button["text"] for row in keyboard["keyboard"] for button in row]
    assert "🔑 Войти" in buttons


def test_login_with_site_phone_and_password_links_telegram(sent):
    user_id = make_user("CUSTOMER", phone="+79991230000")

    handlers.handle_message(message("🔑 Войти"))
    handlers.handle_message(message("8 999 123-00-00"))
    handlers.handle_message(message("secret-pass"))

    db = SessionLocal()
    link = db.query(TelegramAccountLink).filter(TelegramAccountLink.telegram_user_id == CUSTOMER_TG).first()
    db.close()
    assert link is not None and link.user_id == user_id
    # Сообщение с паролем бот сразу удаляет
    assert ("deleteMessage", {"chat_id": CUSTOMER_TG, "message_id": 1}) in sent


def test_wrong_password_does_not_log_in(sent):
    make_user("CUSTOMER", phone="+79991230001")

    handlers.handle_message(message("🔑 Войти"))
    handlers.handle_message(message("+79991230001"))
    handlers.handle_message(message("wrong-pass"))

    assert any("Не удалось войти" in text for text in texts(sent))
    db = SessionLocal()
    assert db.query(TelegramAccountLink).count() == 0
    db.close()


def test_admin_confirms_order_by_button(sent):
    admin_id = make_user("ADMIN", telegram_id=ADMIN_TG, email="admin@woodcommerce.local")
    customer_id = make_user("CUSTOMER", phone="+79991230002")
    order_id = make_order(customer_id)

    handlers.handle_callback(press(f"order:{order_id}:CONFIRMED", ADMIN_TG))

    db = SessionLocal()
    order = db.get(Order, order_id)
    last = (
        db.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == order_id)
        .order_by(OrderStatusHistory.id.desc())
        .first()
    )
    assert order.status == "CONFIRMED"
    assert last.changed_by_id == admin_id
    db.close()


def test_customer_cannot_press_admin_buttons(sent):
    customer_id = make_user("CUSTOMER", telegram_id=CUSTOMER_TG, phone="+79991230003")
    order_id = make_order(customer_id)

    handlers.handle_callback(press(f"order:{order_id}:CONFIRMED", CUSTOMER_TG))

    db = SessionLocal()
    assert db.get(Order, order_id).status == "NEW"
    db.close()
