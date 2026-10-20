from app.services import telegram_service


def test_send_is_skipped_without_token(monkeypatch):
    calls = []
    monkeypatch.setattr(
        telegram_service.requests,
        "post",
        lambda *args, **kwargs: calls.append(args),
    )

    assert telegram_service.send_telegram_message(123, "Тест") is False
    assert calls == []
