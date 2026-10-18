from starlette.datastructures import Headers
from starlette.responses import JSONResponse

MAX_REQUEST_BYTES = 1024 * 1024


class RequestSizeLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        length = headers.get("content-length")

        if length is not None:
            try:
                declared_size = int(length)
            except ValueError:
                declared_size = -1

            if declared_size < 0:
                response = JSONResponse(
                    {"detail": "Invalid Content-Length"},
                    status_code=400,
                )
                await response(scope, receive, send)
                return

            if declared_size > MAX_REQUEST_BYTES:
                response = JSONResponse(
                    {"detail": "Request body too large"},
                    status_code=413,
                )
                await response(scope, receive, send)
                return

        chunks = []
        total = 0

        while True:
            message = await receive()

            if message["type"] == "http.disconnect":
                return

            if message["type"] != "http.request":
                continue

            chunk = message.get("body", b"")
            total += len(chunk)

            if total > MAX_REQUEST_BYTES:
                response = JSONResponse(
                    {"detail": "Request body too large"},
                    status_code=413,
                )
                await response(scope, receive, send)
                return

            chunks.append(chunk)

            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        delivered = False

        async def replay_receive():
            nonlocal delivered

            if not delivered:
                delivered = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }

            return await receive()

        await self.app(scope, replay_receive, send)
