"""Ограничение частоты запросов: защита от подбора пароля и спама заказами.

Счётчики живут в памяти процесса — этого достаточно для одного сервера
(на продакшене API работает одним процессом, см. WEB_CONCURRENCY).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    """Не больше `limit` попыток за `window` секунд на один ключ (IP, Telegram ID)."""

    def __init__(self, name: str, limit: int, window: int):
        self.name = name
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        LIMITERS.append(self)

    def hit(self, key: str) -> int | None:
        """Засчитывает попытку. Если лимит исчерпан — сколько секунд ждать."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return int(hits[0] + self.window - now) + 1
            hits.append(now)
            # Чтобы память не росла от разовых посетителей
            if len(self._hits) > 10_000:
                self._forget_idle(now)
            return None

    def _forget_idle(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def __call__(self, request: Request) -> None:
        """Зависимость FastAPI: лимит по IP покупателя."""
        client_ip = request.client.host if request.client else "unknown"
        retry_after = self.hit(client_ip)
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail=f"Слишком много попыток. Попробуйте через {wait_text(retry_after)}.",
                headers={"Retry-After": str(retry_after)},
            )


LIMITERS: list[RateLimiter] = []


def wait_text(seconds: int) -> str:
    minutes = (seconds + 59) // 60
    return f"{seconds} с" if seconds < 60 else f"{minutes} мин"


def reset_all() -> None:
    for limiter in LIMITERS:
        limiter.reset()


login_limiter = RateLimiter("login", limit=10, window=5 * 60)
register_limiter = RateLimiter("register", limit=5, window=60 * 60)
order_limiter = RateLimiter("orders", limit=30, window=60 * 60)
# Вход через Telegram-бота: ключ — Telegram ID
telegram_login_limiter = RateLimiter("telegram_login", limit=5, window=10 * 60)
