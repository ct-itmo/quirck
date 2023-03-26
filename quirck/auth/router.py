from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import CommaSeparatedStrings
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route, Router

from quirck.auth.jwk import sso_jwks
from quirck.auth.model import User
from quirck.auth.oauth import OAuthException, sso_client
from quirck.core.config import config
from quirck.core.module import app
from quirck.web.template import TemplateResponse

ALLOWED_GROUPS = config('ALLOWED_GROUPS', cast=CommaSeparatedStrings)


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
        redirect_uri=request.url_for("auth:callback"),
        scope="openid profile edu",
        require_prompt=request.query_params.get("prompt") == "1"
    )


async def sso_callback(request: Request) -> Response:
    try:
        token = await sso_client.process_code_flow(
            request,
            redirect_uri=request.url_for("auth:callback")
        )
    except OAuthException as exc:
        return RedirectResponse(f"{request.url_for('auth:failed')}?error=oauth", status_code=303)

    user_info = await sso_jwks.decode(token["id_token"])

    if "isu" not in user_info:
        return RedirectResponse(request.url_for("auth:failed") + "?error=isu", status_code=303)
    
    user_record = parse_user(user_info)

    database: AsyncSession = request.scope["db"]
    user = await database.scalar(select(User).where(User.id == user_record["id"]))

    if user is None:
        if "groups" not in user_info or \
            all(group["name"] not in ALLOWED_GROUPS for group in user_info["groups"]):
            return RedirectResponse(request.url_for("auth:failed") + "?error=group", status_code=303)

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
    request.session.pop("user_id", None)

    base_url = await sso_client.configuration.get_logout_url()
    query_params = {
        "client_id": sso_client.client_id,
        "redirect_uri": request.url_for("auth:logout_complete")
    }

    return RedirectResponse(f"{base_url}?{urlencode(query_params)}", status_code=303)


async def sso_logout_complete(request: Request) -> Response:
    return TemplateResponse(request, "logged_out.html")


sso_router = Router([
    Route("/start", sso_start, name="start"),
    Route("/callback", sso_callback, name="callback"),
    Route("/failed", sso_login_failed, name="failed"),
    Route("/logout", sso_logout, name="logout"),
    Route("/logout/complete", sso_logout_complete, name="logout_complete")
])


__all__ = ["sso_router"]