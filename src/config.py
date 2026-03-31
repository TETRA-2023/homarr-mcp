"""Configuration management for Homarr MCP server."""

import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Get the project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"

# Load .env file from project root
load_dotenv(dotenv_path=ENV_FILE_PATH)


class HomarrSettings(BaseSettings):
    """Homarr MCP server settings with secure API key handling."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    url: str = Field(
        default="http://localhost:7575",
        alias="HOMARR_URL",
        description="Homarr instance base URL",
    )

    api_key: Optional[SecretStr] = Field(
        default=None,
        alias="HOMARR_API_KEY",
        description="Homarr API key (format: <id>.<token>)",
    )

    @property
    def has_api_key(self) -> bool:
        """Check if API key is configured."""
        return self.api_key is not None

    def get_api_key_value(self) -> str:
        """Safely get API key value."""
        if self.api_key is None:
            raise ValueError("HOMARR_API_KEY is required but not set")
        return self.api_key.get_secret_value()


def mask_credential(value: str, visible_chars: int = 2) -> str:
    """Mask a credential for safe logging."""
    if not value:
        return "<empty>"
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    return (
        f"{value[:visible_chars]}{'*' * (len(value) - visible_chars * 2)}{value[-visible_chars:]}"
    )


# Global settings instance (lazy — api_key validated at server startup, not import time)
settings = HomarrSettings()
