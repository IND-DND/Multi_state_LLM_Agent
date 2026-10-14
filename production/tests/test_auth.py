import time
from types import SimpleNamespace

import jwt
import pytest
from conftest import token
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from pydantic import ValidationError

from sql_analytics.auth import TokenVerifier
from sql_analytics.config import Settings


async def test_valid_token(settings):
    assert await TokenVerifier(settings).verify(token()) == ("demo", "analyst-north")


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": 1},
        {"aud": "another-api"},
        {"iss": "attacker"},
        {"nbf": 9999999999},
        {"scp": "other"},
        {"oid": 42},
    ],
)
async def test_invalid_claims(settings, changes):
    with pytest.raises(HTTPException):
        await TokenVerifier(settings).verify(token(**changes))


async def test_invalid_signature(settings):
    with pytest.raises(HTTPException) as exc:
        await TokenVerifier(settings).verify(token(secret="wrong-signature-key-" * 3))
    assert exc.value.status_code == 401


async def test_entra_signature_and_tenant_validation(settings):
    settings.auth_mode = "entra"
    settings.entra_tenant_id = "identity-tenant"
    settings.api_audience = "api-client-id"
    verifier = TokenVerifier(settings)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier.jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key())
    )
    now = int(time.time())
    claims = {
        "oid": "user-object-id",
        "tid": "identity-tenant",
        "iss": "https://login.microsoftonline.com/identity-tenant/v2.0",
        "aud": "api-client-id",
        "iat": now,
        "nbf": now,
        "exp": now + 900,
        "scp": "analytics.access",
    }
    assert await verifier.verify(jwt.encode(claims, key, algorithm="RS256")) == (
        "identity-tenant",
        "user-object-id",
    )
    claims["tid"] = "other-tenant"
    with pytest.raises(HTTPException):
        await verifier.verify(jwt.encode(claims, key, algorithm="RS256"))


def test_production_rejects_demo_and_non_tls():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            auth_mode="demo",
            model_provider="demo",
            control_dsn="postgresql://x",
            query_dsn="postgresql://x",
            checkpoint_dsn="postgresql://x",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            auth_mode="entra",
            model_provider="azure",
            entra_tenant_id="x",
            api_audience="x",
            control_dsn="postgresql://x",
            query_dsn="postgresql://x",
            checkpoint_dsn="postgresql://x",
        )
