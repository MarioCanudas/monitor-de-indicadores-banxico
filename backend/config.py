"""Configuracion central de la aplicacion."""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from .exceptions import ConfigurationError


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    banxico_api: str | None
    mongodb_uri: str | None
    mongodb_database: str
    mongodb_timeout_ms: int
    default_start_date: date
    max_page_size: int

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            banxico_api=os.getenv("BANXICO_API"),
            mongodb_uri=os.getenv("MONGODB_URI"),
            mongodb_database=os.getenv("MONGODB_DATABASE", "banxico_monitor"),
            mongodb_timeout_ms=int(os.getenv("MONGODB_TIMEOUT_MS", "5000")),
            default_start_date=date.fromisoformat(
                os.getenv("DEFAULT_START_DATE", "2024-01-01")
            ),
            max_page_size=int(os.getenv("MAX_PAGE_SIZE", "1000")),
        )

    def require_banxico_api(self) -> str:
        if not self.banxico_api:
            raise ConfigurationError("BANXICO_API no esta configurada.")
        return self.banxico_api

    def require_mongodb_uri(self) -> str:
        if not self.mongodb_uri:
            raise ConfigurationError("MONGODB_URI no esta configurada.")
        return self.mongodb_uri

    @property
    def today(self) -> date:
        return date.today()


def get_settings() -> Settings:
    """Lee la configuracion actual sin exponer valores sensibles."""
    return Settings.from_environment()
