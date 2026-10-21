from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import OutboxMessage


def test_health_check(client: TestClient):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "wood-commerce-api"
    assert data["database"] == "ok"
    assert data["outbox_stuck"] == 0


def test_health_reports_failed_telegram_messages(client: TestClient):
    db = SessionLocal()
    db.add(OutboxMessage(chat_id=1, text="Заказ", status="failed"))
    db.commit()
    db.close()

    assert client.get("/api/v1/health").json()["outbox_failed"] == 1
