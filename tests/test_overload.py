"""Защита от перегрузки: сверх лимита одновременных запросов — сразу 503."""

import asyncio

from app.overload import ConcurrencyLimit


def run(coro):
    return asyncio.run(coro)


def test_requests_over_the_limit_get_503_and_health_always_passes():
    release = asyncio.Event()
    sent: list[dict] = []

    async def slow_app(scope, receive, send):
        await release.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def scenario():
        limited = ConcurrencyLimit(slow_app, limit=2)

        async def call(path, sink):
            async def send(message):
                sink.append(message)
            await limited({"type": "http", "path": path}, None, send)

        busy = [asyncio.create_task(call("/api/v1/products/", [])) for _ in range(2)]
        await asyncio.sleep(0)
        await call("/api/v1/products/", sent)
        health: list[dict] = []
        health_task = asyncio.create_task(call("/api/v1/health", health))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(*busy, health_task)
        # После наплыва счётчик вернулся к нулю — новые запросы снова проходят
        assert limited.active == 0
        return health

    health = run(scenario())

    assert sent[0]["status"] == 503
    assert (b"retry-after", b"30") in sent[0]["headers"]
    assert health[0]["status"] == 200


def test_seo_head_over_the_limit_gets_default_tags_not_503():
    release = asyncio.Event()

    async def slow_app(scope, receive, send):
        await release.wait()

    async def scenario():
        limited = ConcurrencyLimit(slow_app, limit=1)
        busy = asyncio.create_task(limited({"type": "http", "path": "/api/v1/products/"}, None, lambda m: None))
        await asyncio.sleep(0)
        sent: list[dict] = []

        async def send(message):
            sent.append(message)

        query = b"path=/product/5&host=shop.test&scheme=https"
        scope = {"type": "http", "path": "/api/v1/seo/head", "query_string": query}
        await limited(scope, None, send)
        release.set()
        await busy
        return sent

    sent = run(scenario())

    assert sent[0]["status"] == 200
    body = sent[1]["body"].decode()
    assert "<title>" in body and 'href="https://shop.test/product/5"' in body
