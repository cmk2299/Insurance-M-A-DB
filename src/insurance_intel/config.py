"""Loop configuration loaded from environment.

Loaded once at startup. Do not call os.getenv directly anywhere else.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-sonnet-4-6", alias="ANTHROPIC_MODEL")
    anthropic_max_output_tokens: int = Field(2048, alias="ANTHROPIC_MAX_OUTPUT_TOKENS")

    # Nimble
    nimble_api_key: str = Field(..., alias="NIMBLE_API_KEY")
    nimble_bin: str = Field("nimble", alias="NIMBLE_BIN")
    nimble_max_results: int = Field(10, alias="NIMBLE_MAX_RESULTS")

    # Postgres
    postgres_dsn: str = Field(..., alias="POSTGRES_DSN")

    # Notifier (ntfy.sh)
    ntfy_topic_url: str = Field(..., alias="NTFY_TOPIC_URL")

    # Git
    git_repo_dir: Path = Field(..., alias="GIT_REPO_DIR")
    git_autopush: bool = Field(True, alias="GIT_AUTOPUSH")

    # Loop behaviour
    min_events_for_success: int = Field(1, alias="MIN_EVENTS_FOR_SUCCESS")
    coldstart_lookback_days: int = Field(14, alias="COLDSTART_LOOKBACK_DAYS")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_file: Path | None = Field(None, alias="LOG_FILE")

    @property
    def repo_root(self) -> Path:
        """Project root — used to find prompts/, consolidators.yaml, reports/."""
        return Path(__file__).resolve().parents[2]


# Lazy singleton — instantiating Settings() eagerly would break test collection
# and any `--help` invocation in environments without secrets.
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings


class _SettingsProxy:
    """Attribute-proxy so existing `from .config import settings; settings.foo` still works."""

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)


settings = _SettingsProxy()
