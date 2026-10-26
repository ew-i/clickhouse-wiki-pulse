"""Ingester settings, read from environment variables of the same name in upper case."""

from pydantic import Field, HttpUrl, PositiveFloat, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore", frozen=True)

    clickhouse_host: str = "localhost"
    clickhouse_port: int = Field(8123, ge=1, le=65535)
    clickhouse_user: str = "default"
    clickhouse_password: SecretStr = SecretStr("")
    wikimedia_stream_url: HttpUrl = HttpUrl("https://stream.wikimedia.org/v2/stream/recentchange")
    batch_max_rows: PositiveInt = 5000
    batch_max_seconds: PositiveFloat = 5.0
    contact: str = "unknown"

    @property
    def user_agent(self) -> str:
        return f"clickhouse-wiki-pulse/0.1 ({self.contact})"
