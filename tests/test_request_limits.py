from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_normal_health_request():
    response = client.get("/health")
    assert response.status_code == 200


def test_oversized_request_is_rejected():
    payload = b"x" * (1024 * 1024 + 1)

    response = client.post(
        "/v1/tickets/calculate",
        content=payload,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413


def test_small_invalid_request_is_not_rejected_for_size():
    response = client.post(
        "/v1/tickets/calculate",
        content=b"{}",
        headers={"content-type": "application/json"},
    )

    assert response.status_code != 413


def test_large_request_without_content_length():
    from request_limits import (
        MAX_REQUEST_BYTES,
        RequestSizeLimitMiddleware,
    )
    import asyncio

    async def scenario():
        responses = []

        async def inner_app(scope, receive, send):
            await receive()
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await send({
                "type": "http.response.body",
                "body": b"ok",
            })

        middleware = RequestSizeLimitMiddleware(inner_app)

        messages = iter([
            {
                "type": "http.request",
                "body": b"a" * (MAX_REQUEST_BYTES // 2),
                "more_body": True,
            },
            {
                "type": "http.request",
                "body": b"b" * (MAX_REQUEST_BYTES // 2 + 1),
                "more_body": False,
            },
        ])

        async def receive():
            return next(messages)

        async def send(message):
            responses.append(message)

        await middleware(
            {"type": "http", "headers": [], "method": "POST",
             "path": "/", "query_string": b""},
            receive,
            send,
        )

        statuses = [
            message["status"]
            for message in responses
            if message["type"] == "http.response.start"
        ]

        assert statuses == [413]

    asyncio.run(scenario())


def test_small_streamed_request():
    from request_limits import RequestSizeLimitMiddleware
    import asyncio

    async def scenario():
        responses = []
        received = []

        async def inner_app(scope, receive, send):
            message = await receive()
            received.append(message["body"])

            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await send({
                "type": "http.response.body",
                "body": b"ok",
            })

        middleware = RequestSizeLimitMiddleware(inner_app)

        messages = iter([
            {
                "type": "http.request",
                "body": b"hello ",
                "more_body": True,
            },
            {
                "type": "http.request",
                "body": b"world",
                "more_body": False,
            },
        ])

        async def receive():
            return next(messages)

        async def send(message):
            responses.append(message)

        await middleware(
            {"type": "http", "headers": [], "method": "POST",
             "path": "/", "query_string": b""},
            receive,
            send,
        )

        assert received == [b"hello world"]
        assert any(
            message.get("status") == 200
            for message in responses
        )

    asyncio.run(scenario())
