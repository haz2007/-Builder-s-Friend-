"""Сроки хранения (BR-46): что удаляется по сроку, что остаётся, запись в журнал."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import AuditLog, CallbackRequest, Order, OutboxMessage, User
from app.services.retention import DELETED_CUSTOMER_NAME, purge_expired

NOW = datetime(2026, 10, 23, 12, 0)


def days_ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


def message(text: str, status: str, age_days: int) -> OutboxMessage:
    sent_at = days_ago(age_days) if status == "sent" else None
    return OutboxMessage(chat_id=1, text=text, status=status, created_at=days_ago(age_days), sent_at=sent_at)


def callback(name: str, called_days_ago: int | None, age_days: int) -> CallbackRequest:
    status = "NEW" if called_days_ago is None else "DONE"
    handled_at = None if called_days_ago is None else days_ago(called_days_ago)
    return CallbackRequest(name=name, phone="+79990000011", status=status,
                           created_at=days_ago(age_days), handled_at=handled_at)


def test_purge_removes_only_expired_messages_and_callbacks(reset_database):
    db = SessionLocal()
    db.add_all([
        message("старое отправленное", "sent", 8),
        message("свежее отправленное", "sent", 1),
        message("старое неотправленное", "failed", 9),
        # Ещё доставляется — не трогаем, даже если давно в очереди
        message("в очереди", "pending", 9),
        callback("Иван", called_days_ago=31, age_days=40),
        callback("Пётр", called_days_ago=5, age_days=6),
        # Ещё не перезвонили — цель не достигнута
        callback("Анна", called_days_ago=None, age_days=60),
    ])
    db.commit()

    counts = purge_expired(db, now=NOW)
    left_messages = sorted(m.text for m in db.query(OutboxMessage))
    left_callbacks = sorted(c.name for c in db.query(CallbackRequest))
    journal = [entry.summary for entry in db.query(AuditLog).filter(AuditLog.action == "data.purged")]
    db.close()

    assert counts == {"outbox": 2, "callbacks": 1, "orders": 0}
    assert left_messages == ["в очереди", "свежее отправленное"]
    assert left_callbacks == ["Анна", "Пётр"]
    assert journal == [
        "Удалено по сроку хранения: сообщений Telegram — 2, заявок на звонок — 1, заказов без контактов — 0"
    ]


def test_nothing_expired_leaves_no_journal_entry(reset_database):
    db = SessionLocal()
    counts = purge_expired(db, now=NOW)
    entries = db.query(AuditLog).count()
    db.close()

    assert counts == {"outbox": 0, "callbacks": 0, "orders": 0}
    assert entries == 0


def test_deleted_account_keeps_orders_without_contacts(client: TestClient):
    db = SessionLocal()
    customer = User(phone="+79994445577", password_hash=hash_password("my-password"), role="CUSTOMER")
    other = User(phone="+79994445588", password_hash=hash_password("other-pass"), role="CUSTOMER")
    db.add_all([customer, other])
    db.flush()
    delivered = Order(user_id=customer.id, customer_name="Сергей", status="DELIVERED", total_price=600,
                      delivery_method="DELIVERY", delivery_address="Химки, ул. Лесная, 5", comment="после 14:00")
    active = Order(user_id=customer.id, customer_name="Сергей", status="CONFIRMED", total_price=900,
                   delivery_method="DELIVERY", delivery_address="Химки, ул. Лесная, 5", comment="позвонить")
    others = Order(user_id=other.id, customer_name="Ольга", status="DELIVERED", total_price=300,
                   delivery_method="DELIVERY", delivery_address="Москва, ул. Новая, 1")
    db.add_all([delivered, active, others])
    db.commit()
    ids = (customer.id, delivered.id, active.id, others.id)
    db.close()
    customer_id, delivered_id, active_id, others_id = ids
    headers = {"Authorization": f"Bearer {create_access_token(user_id=customer_id, role='CUSTOMER')}"}

    response = client.post("/api/v1/auth/delete-account", json={"password": "my-password"}, headers=headers)

    db = SessionLocal()
    wiped = db.get(Order, delivered_id)
    wiped_now = (wiped.customer_name, wiped.delivery_address, wiped.comment, float(wiped.total_price))
    still_active = db.get(Order, active_id)
    active_contacts = (still_active.customer_name, still_active.delivery_address)
    # Активный заказ доехал уже после удаления аккаунта — его чистит ежедневный проход
    still_active.status = "DELIVERED"
    db.commit()
    counts = purge_expired(db, now=NOW)
    later = db.get(Order, active_id)
    wiped_later = (later.customer_name, later.delivery_address, later.comment)
    untouched = db.get(Order, others_id)
    others_contacts = (untouched.customer_name, untouched.delivery_address)
    db.close()

    assert response.status_code == 200
    assert wiped_now == (DELETED_CUSTOMER_NAME, "", None, 600.0)
    assert active_contacts == ("Сергей", "Химки, ул. Лесная, 5")
    assert counts["orders"] == 1
    assert wiped_later == (DELETED_CUSTOMER_NAME, "", None)
    assert others_contacts == ("Ольга", "Москва, ул. Новая, 1")


def test_purge_works_with_real_clock(reset_database):
    db = SessionLocal()
    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=8)
    db.add(OutboxMessage(chat_id=1, text="старое", status="sent", created_at=old, sent_at=old))
    db.commit()
    counts = purge_expired(db)
    left = db.query(OutboxMessage).count()
    db.close()

    assert counts["outbox"] == 1
    assert left == 0
