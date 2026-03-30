from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette_wtf import CSRFProtectMiddleware

from quirck.auth.router import sso_router
from quirck.core import config
from quirck.core.module import app
from quirck.db.middleware import DatabaseMiddleware
from quirck.web.handlers import exception_handler


def build_app() -> Starlette:
    @asynccontextmanager
    async def lifespan(_):
        yield  # Run app
        if hasattr(app, "shutdown"):
            await app.shutdown()

    return Starlette(
        middleware=[
            Middleware(
                SessionMiddleware,
                secret_key=config.SECRET_KEY,
                session_cookie=config.SESSION_COOKIE_NAME,
                path=config.SESSION_COOKIE_PATH,
            ),
            Middleware(DatabaseMiddleware, url=config.DATABASE_URL, create_tables=True),
            Middleware(CSRFProtectMiddleware, csrf_secret=config.SECRET_KEY),
        ],
        routes=[
            Mount("/auth", sso_router, name="auth"),
            Mount("/static", app=StaticFiles(directory=app.static_path), name="static"),
            app.mount,
        ],
        exception_handlers={Exception: exception_handler},
        lifespan=lifespan,
    )


__all__ = ["build_app"]
