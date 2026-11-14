"""The error envelope (S-12): {"error": {"code", "message", "request_id"}}. No stack trace ever reaches a client."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import logging as applog


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def envelope(request: Request, status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    rid = getattr(request.state, "request_id", "-")
    return JSONResponse({"error": {"code": code, "message": message, "request_id": rid}}, status, headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(request: Request, exc: ApiError):
        return envelope(request, exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        return envelope(request, 422, "VALIDATION", f"{where}: {first.get('msg', 'invalid request')}".strip(": "))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
            exc.status_code, "ERROR")
        return envelope(request, exc.status_code, code, str(exc.detail), getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        applog.event(level="error", msg="unhandled", error=type(exc).__name__, path=request.url.path,
                     request_id=getattr(request.state, "request_id", "-"))
        return envelope(request, 500, "INTERNAL", "Something went wrong. Quote the request id when reporting it.")
