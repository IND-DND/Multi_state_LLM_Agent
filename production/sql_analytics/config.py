from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "production", "test"] = "production"
    auth_mode: Literal["entra", "demo"] = "entra"
    model_provider: Literal["openai", "azure", "ollama", "demo"] = "azure"
    control_dsn: SecretStr
    query_dsn: SecretStr
    checkpoint_dsn: SecretStr
    entra_tenant_id: str = ""
    api_audience: str = ""
    required_scope: str = "analytics.access"
    demo_jwt_secret: SecretStr = SecretStr("")
    model_name: str = ""
    model_base_url: str = "https://api.openai.com/v1"
    model_api_key: SecretStr = SecretStr("")
    azure_endpoint: str = ""
    azure_api_version: str = "2024-10-21"
    max_rows: int = Field(1000, ge=1, le=10000)
    max_result_bytes: int = Field(2_000_000, ge=1024, le=10_000_000)
    statement_timeout_ms: int = Field(10000, ge=100, le=30000)
    request_timeout_seconds: int = Field(45, ge=1, le=120)
    max_model_calls: int = Field(6, ge=1, le=10)
    max_sql_repairs: int = Field(2, ge=0, le=2)
    requests_per_minute: int = Field(20, ge=1, le=1000)
    max_concurrent_queries: int = Field(8, ge=1, le=50)
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "api", "testserver"]

    @model_validator(mode="after")
    def secure_configuration(self):
        if self.environment == "production":
            if self.auth_mode != "entra" or self.model_provider == "demo":
                raise ValueError("Production requires Entra authentication and a real model")
            from psycopg.conninfo import conninfo_to_dict

            for dsn in (self.control_dsn, self.query_dsn, self.checkpoint_dsn):
                if conninfo_to_dict(dsn.get_secret_value()).get("sslmode") != "verify-full":
                    raise ValueError(
                        "Production PostgreSQL connections require sslmode=verify-full"
                    )
        if self.auth_mode == "demo" and len(self.demo_jwt_secret.get_secret_value()) < 32:
            raise ValueError("DEMO_JWT_SECRET must contain at least 32 characters")
        if self.auth_mode == "entra" and (not self.entra_tenant_id or not self.api_audience):
            raise ValueError("ENTRA_TENANT_ID and API_AUDIENCE are required")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
