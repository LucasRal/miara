"""Logging structuré JSON (structlog) avec request_id par requête.

`configure_logging()` est appelé une fois au démarrage (app/main.py).
`request_id_middleware` lie un request_id (entrant via X-Request-ID ou généré)
au contexte structlog de toute la requête et le renvoie dans la réponse.
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response

logger = structlog.get_logger()


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start = time.perf_counter()
    response = await call_next(request)
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((time.perf_counter() - start) * 1000, 1),
    )
    response.headers["X-Request-ID"] = request_id
    return response
