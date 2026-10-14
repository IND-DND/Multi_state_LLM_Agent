import asyncio

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import Principal

bearer = HTTPBearer(auto_error=False)


class TokenVerifier:
    def __init__(self, settings):
        self.settings = settings
        self.jwks = None
        if settings.auth_mode == "entra":
            self.jwks = jwt.PyJWKClient(
                f"https://login.microsoftonline.com/{settings.entra_tenant_id}/discovery/v2.0/keys",
                cache_keys=True,
                lifespan=300,
                timeout=5,
            )

    async def verify(self, token: str) -> tuple[str, str]:
        s = self.settings
        try:
            if len(token) > 16000:
                raise ValueError("Token too large")
            if s.auth_mode == "demo":
                key = s.demo_jwt_secret.get_secret_value()
                algorithm, issuer, audience = "HS256", "sql-analytics-demo", "sql-analytics-api"
            else:
                # The untrusted token cannot choose a JWKS URL or signature algorithm.
                key = (await asyncio.to_thread(self.jwks.get_signing_key_from_jwt, token)).key
                algorithm = "RS256"
                issuer = f"https://login.microsoftonline.com/{s.entra_tenant_id}/v2.0"
                audience = s.api_audience
            claims = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=audience,
                issuer=issuer,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "oid", "tid", "scp"]},
                leeway=10,
            )
            if s.auth_mode == "entra" and claims["tid"] != s.entra_tenant_id:
                raise ValueError("Wrong tenant")
            if s.required_scope not in claims["scp"].split():
                raise HTTPException(403, "missing_api_scope")
            if not isinstance(claims["oid"], str) or not isinstance(claims["tid"], str):
                raise ValueError("Invalid identity")
            return claims["tid"], claims["oid"]
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise HTTPException(
                401, "invalid_access_token", headers={"WWW-Authenticate": "Bearer"}
            ) from exc


async def current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    if credentials is None:
        raise HTTPException(401, "authentication_required", headers={"WWW-Authenticate": "Bearer"})
    tid, subject = await request.app.state.verifier.verify(credentials.credentials)
    principal = await request.app.state.store.principal(tid, subject)
    if principal is None:
        raise HTTPException(403, "principal_not_provisioned")
    return principal


def require(permission: str):
    async def dependency(principal: Principal = Depends(current_principal)):
        if permission not in principal.permissions:
            raise HTTPException(403, "permission_denied")
        return principal

    return dependency
