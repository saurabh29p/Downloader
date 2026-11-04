"""App settings, read from environment variables prefixed with ANYGET_ (and .env)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from anyget import __version__


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ANYGET_", env_file=".env", extra="ignore")

    downloads_dir: Path = Path("./downloads")
    data_dir: Path = Path("./data")
    host: str = "127.0.0.1"
    port: int = 8000

    # Queue
    max_concurrent_downloads: int = Field(default=3, ge=1, le=16)
    max_per_host: int = Field(default=4, ge=1, le=16)
    host_limits: dict[str, int] = Field(default_factory=lambda: {"archive.org": 2})

    # Outgoing HTTP
    contact_email: str = ""
    request_timeout: float = 30.0
    # Explicit outgoing proxy (env HTTP(S)_PROXY is ignored on purpose). When set, the
    # connect-time SSRF check cannot see the final IP; the pre-flight DNS check still runs.
    proxy: str = ""
    # host:port pairs allowed even if they resolve to private IPs. Only for tests and
    # local fixture servers; leave empty in normal use.
    net_allowlist: Annotated[list[str], NoDecode] = Field(default_factory=list)

    api_token: str = Field(default="", repr=False)

    @field_validator("net_allowlist", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'anyget.db'}"

    @property
    def user_agent(self) -> str:
        contact = f"; +mailto:{self.contact_email}" if self.contact_email else ""
        return f"AnyGet/{__version__} (personal downloader{contact})"


@lru_cache
def get_settings() -> Settings:
    return Settings()
