"""Boundaries for untrusted documents and public HTTP requests."""

from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from time import monotonic

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all instructions",
    "system message",
    "developer message",
    "you are chatgpt",
    "reveal your prompt",
    "follow these instructions",
)


def assert_safe_document_text(text: str) -> None:
    lowered = text.casefold()
    if any(marker in lowered for marker in _INJECTION_MARKERS):
        raise ValueError("Document was rejected: it contains prompt-injection-like instructions")


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, access_key: str | None, rate_limit: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.access_key = access_key
        self.rate_limit = rate_limit
        self.requests: defaultdict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path.startswith("/api/"):
            client = request.client.host if request.client else "unknown"
            now = monotonic()
            window = self.requests[client]
            while window and window[0] < now - 60:
                window.popleft()
            if len(window) >= self.rate_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
                )
            window.append(now)
            if self.access_key and request.headers.get("X-API-Key") != self.access_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; connect-src 'self'"
        )
        return response
