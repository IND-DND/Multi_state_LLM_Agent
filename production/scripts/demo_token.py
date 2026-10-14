import os
import sys
import time

import jwt
from dotenv import load_dotenv

load_dotenv()
if os.environ.get("AUTH_MODE") != "demo" or os.environ.get("ENVIRONMENT") == "production":
    raise SystemExit("Demo tokens are disabled")
subject = sys.argv[1] if len(sys.argv) > 1 else "analyst-north"
now = int(time.time())
print(
    jwt.encode(
        {
            "oid": subject,
            "tid": "demo",
            "iss": "sql-analytics-demo",
            "aud": "sql-analytics-api",
            "scp": "analytics.access",
            "iat": now,
            "nbf": now,
            "exp": now + 900,
        },
        os.environ["DEMO_JWT_SECRET"],
        algorithm="HS256",
    )
)
