"""Transactional outbox: уведомления не теряются и не дублируются."""

import threading
import time
from datetime import timedelta

from fastapi.testclient import TestClient
from test_review_request import create_user, headers, link, make_order

from app.database import SessionLocal
from app.models import OutboxMessage
from app.routers import orders as orders_router
from app.services import order_notifications


def outbox_rows():
    db = SessionLocal()
    rows = db.query(OutboxMessage).order_by(OutboxMessage.id).all()
    db.expunge_all()
    db.close()
    return rows


def capture(monkeypatch, result=True):
    sent = []

    def fake_send(chat_id, text, markup=None):
        sent.append((chat_id, text))
        return result

    monkeypatch.setattr(order_notifications, "send_telegram_message", fake_send)
    return sent


def test_messages_survive_a_crash_after_commit(client: TestClient, monkeypatch):
    """Процесс «упал» сразу после сохранения заказа — сообщения ждут в outbox."""
    customer = create_user("CUSTOMER", phone="+79990001122")
    admin = create_user("ADMIN", email="admin@woodcommerce.local")
    link(customer, 1001)
    link(admin, 2002)
    monkeypatch.setattr(orders_router, "deliver_pending", lambda: None)
    sent = capture(monkeypatch)

    make_order(client, customer)

    assert sent == []
    assert {row.chat_id for row in outbox_rows()} == {1001, 2002}
    assert {row.status for row in outbox_rows()} == {"pending"}

    # Следующий проход (бот или API) досылает
    assert order_notifications.deliver_pending() == 2
    assert {chat_id for chat_id, _ in sent} == {1001, 2002}
    assert {row.status for row in outbox_rows()} == {"sent"}


def test_failed_send_is_retried_later(client: TestClient, monkeypatch):
    customer = create_user("CUSTOMER", phone="+79990001122")
    link(customer, 1001)
    capture(monkeypatch, result=False)

    make_order(client, customer)

    row = outbox_rows()[0]
    assert row.status == "pending"
    assert row.attempts == 1
    assert row.next_attempt_at > row.created_at + timedelta(seconds=5)

    # Пока не подошло время — повторной попытки нет
    sent = capture(monkeypatch)
    assert order_notifications.deliver_pending() == 0
    assert sent == []


def test_gives_up_after_max_attempts(reset_database, monkeypatch):
    db = SessionLocal()
    db.add(OutboxMessage(chat_id=1, text="Привет"))
    db.commit()
    db.close()
    capture(monkeypatch, result=False)

    for _ in range(order_notifications.MAX_ATTEMPTS):
        order_notifications.deliver_pending()
        db = SessionLocal()
        db.query(OutboxMessage).update({OutboxMessage.next_attempt_at: OutboxMessage.created_at})
        db.commit()
        db.close()

    row = outbox_rows()[0]
    assert row.status == "failed"
    assert row.attempts == order_notifications.MAX_ATTEMPTS


def test_two_senders_do_not_duplicate(reset_database, monkeypatch):
    """API и бот отправляют одновременно — каждое сообщение уходит один раз."""
    db = SessionLocal()
    db.add_all([OutboxMessage(chat_id=chat_id, text="Заказ") for chat_id in range(20)])
    db.commit()
    db.close()
    sent = []

    def slow_send(chat_id, text, markup=None):
        time.sleep(0.01)
        sent.append(chat_id)
        return True

    monkeypatch.setattr(order_notifications, "send_telegram_message", slow_send)

    threads = [threading.Thread(target=order_notifications.deliver_pending) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(sent) == list(range(20))


def test_status_change_and_review_go_through_outbox(client: TestClient, monkeypatch):
    customer = create_user("CUSTOMER", phone="+79990001122")
    admin = create_user("ADMIN", email="admin@woodcommerce.local")
    link(customer, 1001)
    sent = capture(monkeypatch)
    order_id = make_order(client, customer, method="PICKUP")

    for status in ["CONFIRMED", "PREPARING", "READY_FOR_DELIVERY", "DELIVERED"]:
        client.patch(f"/api/v1/orders/{order_id}/status", json={"status": status}, headers=headers(admin))

    texts = [text for _, text in sent]
    assert any("Выдан" in text for text in texts)
    assert any("отзыв" in text for text in texts)
    assert {row.status for row in outbox_rows()} == {"sent"}
