"""App settings, read from environment variables prefixed with ANYGET_ (and .env)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ANYGET_", env_file=".env", extra="ignore")

    downloads_dir: Path = Path("./downloads")
    data_dir: Path = Path("./data")
    host: str = "127.0.0.1"
    port: int = 8000
    max_concurrent_downloads: int = Field(default=3, ge=1, le=16)
    contact_email: str = ""
    api_token: str = Field(default="", repr=False)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'anyget.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
