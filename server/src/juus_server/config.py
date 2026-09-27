"""Environment-only configuration for the server skeleton."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when required server configuration is absent."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables.

    Secrets are deliberately accepted only from the environment. The example
    values live in ``.env.example`` and are not used as runtime fallbacks.
    """

    environment: str
    model_base_url: str
    model_api_key: str
    model_name: str
    database_url: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from ``environ`` or the process environment."""

        values = os.environ if environ is None else environ
        required = {
            "JUUS_MODEL_BASE_URL": values.get("JUUS_MODEL_BASE_URL", "").strip(),
            "JUUS_MODEL_API_KEY": values.get("JUUS_MODEL_API_KEY", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            missing_text = ", ".join(missing)
            raise ConfigurationError(f"Missing required environment variables: {missing_text}")

        return cls(
            environment=values.get("JUUS_ENV", "development").strip() or "development",
            model_base_url=required["JUUS_MODEL_BASE_URL"],
            model_api_key=required["JUUS_MODEL_API_KEY"],
            model_name=values.get("JUUS_MODEL_NAME", "replace-me").strip() or "replace-me",
            database_url=values.get("JUUS_DATABASE_URL", "sqlite:///data/juus.sqlite3").strip()
            or "sqlite:///data/juus.sqlite3",
        )
