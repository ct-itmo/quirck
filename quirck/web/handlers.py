import traceback

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from quirck.core import config
from quirck.web.template import TemplateResponse


def exception_handler(request: Request, exc: Exception) -> Response:
    if config.DEBUG:
        tb = "\n".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    else:
        tb = None

    if not isinstance(exc, HTTPException):
        exc = HTTPException(status_code=500, detail="На сервере проблема. Повторите запрос или напишите в чат.")

    return TemplateResponse(
        request,
        "error.html",
        {
            "traceback": tb,
            "error": exc.detail,
        },
        status_code=exc.status_code,
    )


__all__ = ["exception_handler"]
