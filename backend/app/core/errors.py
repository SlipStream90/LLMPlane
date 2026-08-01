"""RFC 7807 ``application/problem+json`` error handling.

Every error body in the control-plane API has the same shape
(api-contracts.md 2). Routes raise `ProblemException` (or plain
`HTTPException`); the handlers registered here render both into problem+json.
No route builds an ad hoc error body.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"

_DEFAULT_TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    413: "Payload Too Large",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


class ProblemException(Exception):
    """Application error carrying everything an RFC 7807 body needs."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        title: str | None = None,
        type_: str = "about:blank",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.title = title or _DEFAULT_TITLES.get(status_code, "Error")
        self.type = type_
        self.extra = extra or {}


class NotFoundProblem(ProblemException):
    def __init__(self, resource: str, identifier: Any) -> None:
        super().__init__(
            status.HTTP_404_NOT_FOUND,
            f"{resource} '{identifier}' was not found.",
            type_="https://llmplane.dev/problems/not-found",
        )


class ConflictProblem(ProblemException):
    def __init__(self, detail: str, extra: dict[str, Any] | None = None) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT,
            detail,
            type_="https://llmplane.dev/problems/conflict",
            extra=extra,
        )


class ValidationProblem(ProblemException):
    def __init__(self, detail: str, extra: dict[str, Any] | None = None) -> None:
        super().__init__(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail,
            type_="https://llmplane.dev/problems/validation",
            extra=extra,
        )


class UpstreamProblem(ProblemException):
    """A dependency we do not control (gateway, provider, Langfuse, Docker)
    failed. Distinguished from our own 500s so operators can tell whose fault
    an incident is."""

    def __init__(
        self, detail: str, status_code: int = status.HTTP_502_BAD_GATEWAY
    ) -> None:
        super().__init__(
            status_code,
            detail,
            type_="https://llmplane.dev/problems/upstream-failure",
        )


def _problem_response(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    type_: str = "about:blank",
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": type_,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": str(request.url.path),
    }
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status_code, media_type=PROBLEM_CONTENT_TYPE)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemException)
    async def _problem_handler(request: Request, exc: ProblemException) -> JSONResponse:
        return _problem_response(
            request, exc.status_code, exc.title, exc.detail, exc.type, exc.extra
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _problem_response(
            request,
            exc.status_code,
            _DEFAULT_TITLES.get(exc.status_code, "Error"),
            detail,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _problem_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Unprocessable Entity",
            "Request body or parameters failed validation.",
            "https://llmplane.dev/problems/validation",
            {"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the real cause; never leak internals (which may embed a DSN or a
        # provider error containing a key fragment) to the client.
        logger.exception("Unhandled error on %s", request.url.path)
        return _problem_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal Server Error",
            "An unexpected error occurred. The incident has been logged.",
        )
