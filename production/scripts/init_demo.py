"""Generate untracked random local credentials; never overwrite an existing .env."""

import secrets
from pathlib import Path

path = Path(".env")
if path.exists():
    raise SystemExit(".env already exists; leaving it unchanged")
passwords = {
    name: secrets.token_urlsafe(32)
    for name in (
        "POSTGRES_PASSWORD",
        "QUERY_DB_PASSWORD",
        "CONTROL_DB_PASSWORD",
        "CHECKPOINT_DB_PASSWORD",
        "DEMO_JWT_SECRET",
    )
}
lines = [
    "ENVIRONMENT=development",
    "AUTH_MODE=demo",
    "MODEL_PROVIDER=demo",
    "POSTGRES_DB=analytics",
]
lines.extend(f"{key}={value}" for key, value in passwords.items())
for key, user, pw in [
    ("MIGRATION_DSN", "postgres", "POSTGRES_PASSWORD"),
    ("QUERY_DSN", "analytics_gateway", "QUERY_DB_PASSWORD"),
    ("CONTROL_DSN", "analytics_control", "CONTROL_DB_PASSWORD"),
    ("CHECKPOINT_DSN", "analytics_checkpoint", "CHECKPOINT_DB_PASSWORD"),
]:
    lines.append(f"{key}=postgresql://{user}:{passwords[pw]}@db:5432/analytics")
path.write_text("\n".join(lines) + "\n")
path.chmod(0o600)
print("Created .env with random local credentials. Start with docker compose up --build.")
