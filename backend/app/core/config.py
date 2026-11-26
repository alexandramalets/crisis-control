from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "production", "test"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    host: str = "0.0.0.0"
    port: int = Field(8000, ge=1, le=65535)

    db_host: str = "localhost"
    db_port: int = Field(5432, ge=1, le=65535)
    db_name: str = "crisis_analytics"
    db_user: str = "crisis_app"
    db_password: SecretStr = Field(min_length=1)
    db_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "prefer"
    db_sslrootcert: Path | None = None
    db_startup_retries: int = Field(10, ge=1)
    db_startup_retry_delay: float = Field(2.0, gt=0)
    db_connect_timeout: int = Field(5, ge=1)
    db_pool_size: int = Field(5, ge=1)
    db_max_overflow: int = Field(10, ge=0)
    db_echo: bool = False
    db_migrate_on_startup: bool = False

    analytics_service_url: str = "http://localhost:8001"
    analytics_service_key: SecretStr = Field(min_length=32)
    analytics_tls_ca_file: Path | None = None
    analytics_timeout_seconds: float = Field(30.0, gt=0, le=300)
    analytics_max_payload_bytes: int = Field(2 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    analytics_breaker_failures: int = Field(3, ge=1, le=20)
    analytics_breaker_reset_seconds: float = Field(30.0, gt=0, le=600)
    analytics_retries: int = Field(1, ge=0, le=3)

    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_issuer: str = "crisis-analytics"
    jwt_audience: str = "crisis-analytics-api"
    access_token_ttl_minutes: int = Field(15, ge=1, le=60)
    refresh_token_ttl_days: int = Field(7, ge=1, le=30)
    # False допустимо только при разработке по HTTP без localhost
    refresh_cookie_secure: bool = True

    login_max_failures: int = Field(5, ge=1)
    login_lock_minutes: int = Field(15, ge=1)
    allow_registration: bool = False

    cors_origins: str = ""

    # Пустые значения оставляют HTTP. Для стенда с TLS задаются вместе с REQUIRE_TLS.
    tls_cert_file: Path | None = None
    tls_key_file: Path | None = None
    tls_ca_file: Path | None = None
    require_tls: bool = False

    # Каталог загруженных файлов (staging и зашифрованные оригиналы). Создаётся при запуске.
    data_dir: Path = Path("data")
    dataset_encryption_key: SecretStr = Field(min_length=32)
    upload_max_bytes: int = Field(10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    upload_max_rows: int = Field(20_000, ge=1, le=100_000)
    upload_staging_ttl_minutes: int = Field(60, ge=5, le=24 * 60)

    @field_validator(
        "db_sslrootcert", "analytics_tls_ca_file", "tls_cert_file", "tls_key_file", "tls_ca_file",
        mode="before",
    )
    @classmethod
    def empty_path_is_none(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @field_validator("cors_origins")
    @classmethod
    def cors_rejects_wildcard(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if "*" in origins:
            raise ValueError("CORS_ORIGINS не может быть *: укажите конкретные источники")
        return value

    @property
    def database_url(self) -> URL:
        query = {"sslmode": self.db_sslmode}
        if self.db_sslrootcert is not None:
            query["sslrootcert"] = str(self.db_sslrootcert)
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query=query,
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
