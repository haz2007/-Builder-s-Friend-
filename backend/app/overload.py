"""Защита от перегрузки: не больше N запросов к API одновременно.

Без лимита при наплыве запросы копятся в очереди к пулу потоков: клиенты
давно ушли, а сервер ещё минутами разбирает их по одному, и новые посетители
ждут. Лишним сразу отвечаем 503 с Retry-After — сайт остаётся живым для тех,
кто уже внутри, и сам восстанавливается, как только наплыв спадёт
(нагрузочный тест — benchmarks/load/README.md).
"""

import json
from urllib.parse import parse_qs

from starlette.types import ASGIApp, Receive, Scope, Send

# Потоков у обработчиков 40, соединений с базой 15: небольшая очередь сверху
# допустима, длинная — нет
MAX_IN_FLIGHT = 48
# Проверку здоровья пропускаем всегда — по ней видно, что сервер жив
EXEMPT_PATHS = {"/api/v1/health"}
SEO_HEAD_PATH = "/api/v1/seo/head"


class ConcurrencyLimit:
    def __init__(self, app: ASGIApp, limit: int = MAX_IN_FLIGHT) -> None:
        self.app = app
        self.limit = limit
        self.active = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return
        if self.active >= self.limit:
            if scope["path"] == SEO_HEAD_PATH:
                # Caddy вставляет этот ответ в каждую страницу: вместо 503 —
                # общие теги, иначе страница оборвалась бы на середине
                await send_seo_fallback(scope, send)
            else:
                await reject(send)
            return
        self.active += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.active -= 1


async def reject(send: Send) -> None:
    body = json.dumps({"detail": "Сервер перегружен, попробуйте через минуту."}, ensure_ascii=False).encode()
    await send({
        "type": "http.response.start",
        "status": 503,
        "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"retry-after", b"30"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": body})


async def send_seo_fallback(scope: Scope, send: Send) -> None:
    from .routers.seo import default_head

    query = parse_qs(scope.get("query_string", b"").decode())

    def arg(name: str, default: str) -> str:
        return (query.get(name) or [default])[0][:300]

    body = default_head(arg("path", "/"), arg("host", "localhost"), arg("scheme", "https")).encode()
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/html; charset=utf-8"), (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})
