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


def test_api_url_defaults_to_telegram(monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_URL", raising=False)

    assert telegram_service.telegram_api_url("1:abc") == "https://api.telegram.org/bot1:abc"


def test_api_url_can_point_to_relay(monkeypatch):
    """Если api.telegram.org закрыт с сервера — запросы идут через посредника."""
    monkeypatch.setenv("TELEGRAM_API_URL", "https://telegram-relay.shop.workers.dev/")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:abc")
    sent = []

    class Reply:
        def json(self):
            return {"ok": True}

    monkeypatch.setattr(
        telegram_service.requests,
        "post",
        lambda url, **kwargs: sent.append(url) or Reply(),
    )

    assert telegram_service.send_telegram_message(123, "Тест") is True
    assert sent == ["https://telegram-relay.shop.workers.dev/bot1:abc/sendMessage"]
