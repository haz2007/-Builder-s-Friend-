
import json
import os
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def send_telegram_message(message: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram: не найден токен или chat_id в backend/.env")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
    }).encode("utf-8")

    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(
            request,
            context=SSL_CONTEXT,
            timeout=10,
        ) as response:
            result = json.loads(response.read().decode("utf-8"))

            if result.get("ok"):
                print("Telegram: сообщение отправлено")
                return True

            print("Telegram API отклонил сообщение:", result.get("description"))
            return False

    except HTTPError as error:
        try:
            result = json.loads(error.read().decode("utf-8"))
            print(
                "Telegram HTTP ошибка:",
                error.code,
                result.get("description", "Причина не указана"),
            )
        except (ValueError, OSError):
            print("Telegram HTTP ошибка:", error.code)

        return False

    except (URLError, TimeoutError, OSError, ValueError) as error:
        print("Telegram: ошибка соединения или ответа:", repr(error))
        return False
