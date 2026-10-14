import time

import jwt
import pytest

from sql_analytics.config import Settings

SECRET = "unit-test-secret-only-" * 3


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        environment="test",
        auth_mode="demo",
        model_provider="demo",
        demo_jwt_secret=SECRET,
        control_dsn="postgresql://unused",
        query_dsn="postgresql://unused",
        checkpoint_dsn="postgresql://unused",
    )


def token(subject="analyst-north", secret=SECRET, **overrides):
    now = int(time.time())
    claims = {
        "oid": subject,
        "tid": "demo",
        "iss": "sql-analytics-demo",
        "aud": "sql-analytics-api",
        "scp": "analytics.access",
        "iat": now,
        "nbf": now,
        "exp": now + 900,
    }
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")
