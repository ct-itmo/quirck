"""Basic OAuth2 / OpenID Connect implementation.

Unfortunately, authlib is a huge mess. So here we go."""

import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from starlette.requests import Request
from starlette.responses import RedirectResponse

from quirck.core.config import config

logger = logging.getLogger(__name__)


class OAuthException(ValueError): ...


class OAuthConfiguration:
    async def get_access_token_url(self) -> str:
        raise NotImplementedError()
    
    async def get_authorize_url(self) -> str:
        raise NotImplementedError()

    async def get_jwks_url(self) -> str:
        raise NotImplementedError()

    async def get_issuer(self) -> str:
        raise NotImplementedError()

    async def get_logout_url(self) -> str:
        raise NotImplementedError()


class StaticOAuthConfiguration(OAuthConfiguration):
    def __init__(self, access_token_url: str, authorize_url: str, issuer: str | None = None):
        self.access_token_url = access_token_url
        self.authorize_url = authorize_url
        self.issuer = issuer

    async def get_access_token_url(self) -> str:
        return self.access_token_url

    async def get_authorize_url(self) -> str:
        return self.authorize_url

    async def get_issuer(self) -> str | None:
        return self.issuer


class WellKnownConfiguration(OAuthConfiguration):
    metadata: dict[str, Any]
    is_cached: bool

    def __init__(self, server_metadata_url: str):
        self.server_metadata_url = server_metadata_url
        self.is_cached = False
        self.metadata = {}

    async def _preload(self) -> None:
        if self.is_cached:
            return

        response = httpx.get(self.server_metadata_url)
        if response.status_code != httpx.codes.OK:
            raise OAuthException(f"Remote server returned error code {response.status_code} for {self.server_metadata_url}")

        self.metadata = response.json()

    async def get_access_token_url(self) -> str:
        await self._preload()
        return self.metadata["token_endpoint"]

    async def get_authorize_url(self) -> str:
        await self._preload()
        return self.metadata["authorization_endpoint"]

    async def get_issuer(self) -> str:
        await self._preload()
        return self.metadata["issuer"]

    async def get_jwks_url(self) -> str:
        await self._preload()
        return self.metadata["jwks_uri"]

    async def get_logout_url(self) -> str:
        await self._preload()
        return self.metadata["end_session_endpoint"]



class OAuthClient:
    def __init__(self, configuration: OAuthConfiguration, client_id: str, client_secret: str, **kwargs):
        self.client_id = client_id
        self.client_secret = client_secret
        self.configuration = configuration

    async def authorize_redirect(self, request: Request, *, redirect_uri: str, scope: str,
                                 response_type: str = "code", require_prompt: bool = False) -> RedirectResponse:
        base_url = await self.configuration.get_authorize_url()

        state = secrets.token_hex(32) # CSRF protection as of RFC6749
        request.session["state"] = state

        query_params: dict[str, Any] = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope,
            "response_type": response_type
        }

        if require_prompt:
            query_params["prompt"] = "login"

        return RedirectResponse(f"{base_url}?{urlencode(query_params)}", status_code=303)

    async def process_code_flow(self, request: Request, redirect_uri: str) -> dict[str, Any]:
        base_url = await self.configuration.get_access_token_url()
        
        session_state = request.session.get("state", None)
        response_state = request.query_params.get("state", None)

        if not session_state or session_state != response_state:
            raise OAuthException("Malformed state")

        code = request.query_params.get("code", None)
        if not code:
            raise OAuthException("Missing code")

        token_request = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "state": response_state,
            "redirect_uri": redirect_uri
        }

        response = httpx.post(
            base_url,
            data=token_request,
            headers={"Accept": "application/json"}
        )

        if response.status_code != httpx.codes.OK:
            logger.warn("URL: %s, Response: %s", response.status_code, response.text)
            raise OAuthException(f"Remote server returned error code {response.status_code}")

        token_response = response.json()

        return token_response


sso_configuration = WellKnownConfiguration(server_metadata_url=config("SSO_CONFIGURATION_URL", cast=str))

sso_client = OAuthClient(
    configuration=sso_configuration,
    client_id=config("SSO_CLIENT_ID", cast=str),
    client_secret=config("SSO_CLIENT_SECRET", cast=str)
)


__all__ = ["OAuthClient", "sso_configuration", "sso_client"]
