# Образ для API и Telegram-бота (бот запускается из того же образа другой командой)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Запуск не от root
RUN useradd --create-home --uid 1000 app \
    && mkdir -p uploads/products \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Перед стартом API приводим базу в актуальное состояние
CMD ["sh", "-c", "python manage.py migrate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-1} --proxy-headers --forwarded-allow-ips='*'"]
