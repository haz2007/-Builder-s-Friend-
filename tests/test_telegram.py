
from app.services.telegram_service import send_telegram_message

result = send_telegram_message("Тест Telegram — Друг Строителя")

print("Сообщение отправлено:", result)
