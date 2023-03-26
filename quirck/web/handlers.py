import traceback
from typing import Any

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from quirck.core import config
from quirck.web.template import TemplateResponse


def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    return TemplateResponse(
        request,
        "error.html",
        {
            "traceback": traceback.format_exception(type(exc), exc, exc.__traceback__) if config.DEBUG else None,
            "error": exc.detail
        },
        status_code=exc.status_code
    )


def base_exception_handler(request: Request, exc: Exception) -> Response:
    return TemplateResponse(
        request,
        "error.html",
        {
            "traceback": exc if config.DEBUG else None,
            "error": "На сервере проблема. Повторите запрос или напишите в чат.",
        },
        status_code=500
    )


__all__ = ["http_exception_handler", "base_exception_handler"]
