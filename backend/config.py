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
    alert_medium_threshold_pct: float
    alert_high_threshold_pct: float
    azure_openai_api_key: str | None
    azure_openai_endpoint: str | None
    azure_openai_deployment: str
    azure_openai_api_version: str
    gmail_user: str | None
    gmail_key: str | None

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
            alert_medium_threshold_pct=float(os.getenv("ALERT_MEDIUM_THRESHOLD_PCT", "2")),
            alert_high_threshold_pct=float(os.getenv("ALERT_HIGH_THRESHOLD_PCT", "5")),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_deployment=os.getenv(
                "AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini-ejercicio-openai"
            ),
            azure_openai_api_version=os.getenv(
                "AZURE_OPENAI_API_VERSION", "2024-10-21"
            ),
            gmail_user=os.getenv("GMAIL_USER") or os.getenv("GMAIL_EMAIL"),
            gmail_key=os.getenv("GMAIL_KEY"),
        )

    def require_banxico_api(self) -> str:
        if not self.banxico_api:
            raise ConfigurationError("BANXICO_API no esta configurada.")
        return self.banxico_api

    def require_mongodb_uri(self) -> str:
        if not self.mongodb_uri:
            raise ConfigurationError("MONGODB_URI no esta configurada.")
        return self.mongodb_uri

    def require_azure_openai(self) -> tuple[str, str]:
        if not self.azure_openai_api_key or not self.azure_openai_endpoint:
            raise ConfigurationError(
                "AZURE_OPENAI_API_KEY y AZURE_OPENAI_ENDPOINT son requeridos."
            )
        return self.azure_openai_api_key, self.azure_openai_endpoint

    def require_gmail(self) -> tuple[str, str]:
        if not self.gmail_user or not self.gmail_key:
            raise ConfigurationError("GMAIL_USER y GMAIL_KEY son requeridos.")
        return self.gmail_user, self.gmail_key

    @property
    def today(self) -> date:
        return date.today()


def get_settings() -> Settings:
    """Lee la configuracion actual sin exponer valores sensibles."""
    return Settings.from_environment()
