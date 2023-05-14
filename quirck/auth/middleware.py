import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Send, Scope

from quirck.auth.model import User
from quirck.web.template import TemplateResponse

logger = logging.getLogger(__name__)


class AuthenticationMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            session: dict[str, str] = scope["session"]

            if "user_id" in session:
                db: AsyncSession = scope["db"]
                user = (await db.scalars(
                    select(User).where(User.id == session["user_id"])
                )).one_or_none()

                if user is None:
                    logger.warn("Unknown user %d with valid session, logging out", session["user_id"])
                    del session["user_id"]

                scope["user"] = user
            
            if "user_id" not in session:
                response = TemplateResponse(Request(scope), "anonymous.html", status_code=403)
                return await response(scope, receive, send)

        return await self.app(scope, receive, send)


class AdminMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            session: dict[str, str] = scope["session"]
            user: User = scope["user"]

            if "origin_user_id" not in session and not user.is_admin:
                response = TemplateResponse(Request(scope), "error.html", {"error": "Недостаточно прав"}, status_code=403)
                return await response(scope, receive, send)

            return await self.app(scope, receive, send)


__all__ = ["AuthenticationMiddleware", "AdminMiddleware"]
