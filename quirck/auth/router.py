import logging

from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import CommaSeparatedStrings
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Mount, Route, Router

from quirck.auth.form import ImpersonateForm
from quirck.auth.jwk import sso_jwks
from quirck.auth.middleware import AdminMiddleware, AuthenticationMiddleware
from quirck.auth.model import User
from quirck.auth.oauth import OAuthException, sso_client
from quirck.core.config import config
from quirck.core.module import app
from quirck.web.template import TemplateResponse

ALLOWED_GROUPS = config('ALLOWED_GROUPS', cast=CommaSeparatedStrings)
logger = logging.getLogger(__name__)


def parse_user(user_info: dict[str, Any]) -> dict[str, Any]:
    groups = user_info.get("groups", [])
    if len(groups) > 0:
        group = groups[0].get("name", None)
    else:
        group = None

    return {
        "id": user_info["isu"],
        "name": user_info["name"],
        "group": group
    }


async def sso_start(request: Request) -> Response:
    return await sso_client.authorize_redirect(
        request,
        redirect_uri=str(request.url_for("auth:callback")),
        scope="openid profile edu",
        require_prompt=request.query_params.get("prompt") == "1"
    )


async def sso_callback(request: Request) -> Response:
    try:
        token = await sso_client.process_code_flow(
            request,
            redirect_uri=str(request.url_for("auth:callback"))
        )
    except OAuthException as exc:
        logger.info("Authorization failed: %s", exc)
        return RedirectResponse(f"{request.url_for('auth:failed')}?error=oauth", status_code=303)

    user_info = await sso_jwks.decode(token["id_token"])

    if "isu" not in user_info:
        return RedirectResponse(f"{request.url_for('auth:failed')}?error=isu", status_code=303)

    user_record = parse_user(user_info)

    database: AsyncSession = request.scope["db"]
    user = await database.scalar(select(User).where(User.id == user_record["id"]))

    if user is None:
        can_register = False

        if not can_register and hasattr(app, "validate_new_user"):
            can_register = await app.validate_new_user(user_record)

        if not can_register and len(ALLOWED_GROUPS) > 0:
            can_register = "*" in ALLOWED_GROUPS or \
                "groups" in user_info and any(group["name"] in ALLOWED_GROUPS for group in user_info["groups"])

        if not can_register:
            return RedirectResponse(f"{request.url_for('auth:failed')}?error=group", status_code=303)

    statement = insert(User).values([user_record])
    statement = statement.on_conflict_do_update(
        index_elements=[User.id],
        set_=dict(
            name=statement.excluded.name,
            group=statement.excluded.group
        )
    ).returning(User)

    user = (await database.scalars(statement, execution_options={"populate_existing": True})).one()

    request.session["user_id"] = user.id

    return RedirectResponse(request.url_for(app.main_route), status_code=303)


async def sso_login_failed(request: Request) -> Response:
    match request.query_params.get("error", ""):
        case "oauth":
            error = "Вы не авторизовались в ITMO ID."
        case "isu" | "group":
            error = "Вы не записаны на курс."
        case _:
            error = "Произошла неизвестная ошибка."

    return TemplateResponse(request, "auth_error.html", {"error": error}, status_code=403)


async def sso_logout(request: Request) -> Response:
    if "origin_user_id" in request.session:
        logger.info("User %s is logged out from %s", request.session["origin_user_id"], request.session["user_id"])
        request.session["user_id"] = request.session.pop("origin_user_id")
        return RedirectResponse(request.url_for(app.main_route), status_code=303)

    request.session.pop("user_id", None)

    base_url = await sso_client.configuration.get_logout_url()
    query_params = {
        "client_id": sso_client.client_id,
        "redirect_uri": request.url_for("auth:logout_complete")
    }

    return RedirectResponse(f"{base_url}?{urlencode(query_params)}", status_code=303)


async def sso_logout_complete(request: Request) -> Response:
    return TemplateResponse(request, "logged_out.html")


async def check_user_exists(request: Request, user_id: int) -> bool:
    database: AsyncSession = request.scope["db"]
    return await database.scalar(select(User).where(User.id == user_id)) is not None


async def impersonate(request: Request) -> Response:
    form = await ImpersonateForm.from_formdata(request)

    if await form.validate_on_submit():
        logger.info("User %s is impersonating as %s", request.session["user_id"], form.user_id.data)
        request.session["origin_user_id"] = request.session.pop("user_id")
        request.session["user_id"] = form.user_id.data

        return RedirectResponse(request.url_for(app.main_route), status_code=303)

    return TemplateResponse(request, "impersonate.html", {"form": form})


sso_router = Router([
    Route("/start", sso_start, name="start"),
    Route("/callback", sso_callback, name="callback"),
    Route("/failed", sso_login_failed, name="failed"),
    Route("/logout", sso_logout, name="logout"),
    Route("/logout/complete", sso_logout_complete, name="logout_complete"),
    Mount(
        "/admin",
        routes=[
            Route("/impersonate", impersonate, name="impersonate", methods=["GET", "POST"])
        ],
        middleware=[
            Middleware(AuthenticationMiddleware),
            Middleware(AdminMiddleware)
        ],
        name="admin"
    )
])


__all__ = ["sso_router"]
