"""PyJWT can't fetch tokens async, so here we go."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
import jwt

from quirck.auth.oauth import OAuthConfiguration, sso_configuration
from quirck.core.config import SSO_CLIENT_ID

CACHE_TTL = timedelta(hours=4)


class JWKSError(ValueError): ...

class JWTMalformedToken(ValueError): ...


@dataclass
class JWTKeyInfo:
    key: str
    algorithm: str


class JWKS:
    key_cache: dict[str, dict[str, Any]]
    last_update: datetime | None

    def __init__(self, configuration: OAuthConfiguration, audience: str):
        self.configuration = configuration
        self.key_cache = {}
        self.last_update = None
        self.audience = audience

    @staticmethod
    def detect_alg(key_data: dict[str, Any]) -> str:
        kty = key_data["kty"]

        if "alg" in key_data:
            return key_data["alg"]

        crv = key_data.get("crv", None)
        if kty == "EC":
            if crv == "P-256" or not crv:
                algorithm = "ES256"
            elif crv == "P-384":
                algorithm = "ES384"
            elif crv == "P-521":
                algorithm = "ES512"
            elif crv == "secp256k1":
                algorithm = "ES256K"
            else:
                raise JWKSError(f"Unsupported crv: {crv}")
        elif kty == "RSA":
            algorithm = "RS256"
        elif kty == "oct":
            algorithm = "HS256"
        elif kty == "OKP":
            if not crv:
                raise JWKSError(f"crv is not found: {key_data}")
            if crv == "Ed25519":
                algorithm = "EdDSA"
            else:
                raise JWKSError(f"Unsupported crv: {crv}")
        else:
            raise JWKSError(f"Unsupported kty: {kty}")

        return algorithm

    async def fetch_keys(self, force_update: bool = False) -> bool:
        """Returns True if keys were updated and False if they were returned from cache."""
        if not force_update and self.last_update and datetime.now() - self.last_update < CACHE_TTL:
            return False

        self.last_update = datetime.now()
        url = await self.configuration.get_jwks_url()

        response = httpx.get(url, headers={"Accept": "application/json"})
        if response.status_code != httpx.codes.OK:
            raise JWKSError("JWKS server is unavailable")

        self.key_cache = {
            key["kid"]: key
            for key in response.json()["keys"]
        }

        return True

    async def get_key(self, kid: str, force_update: bool = False) -> JWTKeyInfo:
        updated = await self.fetch_keys(force_update)
        key = self.key_cache.get(kid)

        if key is None:
            if not updated:
                return await self.get_key(kid, force_update=True)

            raise JWTMalformedToken(f"Unknown or revoked kid: {kid}")

        jwk = jwt.PyJWK(key)

        return JWTKeyInfo(jwk.key, JWKS.detect_alg(key))

    async def decode(self, token: str) -> dict[str, Any]:
        header = jwt.get_unverified_header(token)
        if "kid" not in header:
            raise JWTMalformedToken("Key identifier is missing")

        key = await self.get_key(header["kid"])

        return jwt.decode(
            token,
            key.key,
            algorithms=[key.algorithm],
            issuer=await self.configuration.get_issuer(),
            audience=self.audience
        )


sso_jwks = JWKS(sso_configuration, audience=SSO_CLIENT_ID)


__all__ = ["JWKS", "sso_jwks"]
