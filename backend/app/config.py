"""Settings read once from the environment and the repository's `.env`.

This is the only module that reads environment variables. Everything else asks
`get_settings()`.
"""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        # Blank lines in .env such as `EXTRACT_MODEL=` mean "not set", not "empty string".
        env_ignore_empty=True,
        extra="ignore",
    )

    # Clio Manage
    clio_base_url: str = "https://app.clio.com"
    # Pinned so a change of Clio's default minor version cannot change field meanings.
    clio_api_version: str = "4.0.13"
    clio_client_id: str | None = None
    clio_client_secret: SecretStr | None = None
    clio_redirect_uri: str = "http://127.0.0.1:8000/oauth/callback"
    clio_matter_query: str | None = None
    # Tries per Clio request; rate limits, 5xx and dropped connections are retried.
    clio_max_attempts: int = Field(default=6, ge=1)
    # Clio caps list pages at 200 records.
    clio_page_limit: int = Field(default=200, ge=1, le=200)
    clio_timeout_seconds: float = Field(default=60, gt=0)
    clio_download_timeout_seconds: float = Field(default=120, gt=0)
    # Connection-level retries inside httpx, below the request retries above.
    clio_transport_retries: int = Field(default=2, ge=0)
    clio_token_timeout_seconds: float = Field(default=30, gt=0)
    clio_oauth_callback_seconds: int = Field(default=300, ge=1)

    # Models. Prices are USD per million tokens.
    # Wire format of the model API: "anthropic" (Messages API), "openai" (Chat
    # Completions), or "gemini" (Google's generateContent, D30).
    llm_provider: Literal["anthropic", "openai", "gemini"] = "anthropic"
    # Leave unset for the provider's public endpoint.
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_max_output_tokens: int = Field(default=4096, ge=256)
    extract_model: str | None = None
    merge_model: str | None = None
    extract_price_in: Decimal | None = None
    extract_price_out: Decimal | None = None
    merge_price_in: Decimal | None = None
    merge_price_out: Decimal | None = None
    extract_concurrency: int = Field(default=8, ge=1)
    llm_timeout_seconds: float = Field(default=180, gt=0)
    # Most HTTP attempts per minute to each role's model, retries included; 0 is no
    # limit. Enforced per process, so only one process may call models during a run.
    extract_rpm: int = Field(default=0, ge=0)
    merge_rpm: int = Field(default=0, ge=0)
    # Added to the 60/rpm seconds between attempts, for clock skew at the API's end.
    llm_rate_margin_seconds: float = Field(default=1.0, ge=0)
    # The longest wait a 429 or 503 may ask for; a longer one fails the call at once.
    llm_max_retry_wait_seconds: float = Field(default=120, gt=0)
    # Tries per model call on rate limits, overload and dropped connections.
    llm_max_attempts: int = Field(default=5, ge=1)
    # Inputs extracted, and facts scored, per committed batch.
    extract_batch_size: int = Field(default=40, ge=1)
    score_batch_size: int = Field(default=50, ge=1)
    # Rounds of asking again about facts the scorer leaves out of a batch.
    score_passes: int = Field(default=2, ge=1)
    # Facts, by significance, the brief model sees besides the ones always included.
    brief_fact_limit: int = Field(default=40, ge=1)

    # Storage
    data_dir: Path = Path("data")

    # App
    frontend_origin: str = "http://localhost:5173"
    share_default_expiry_days: int = Field(default=30, ge=1)

    @field_validator("data_dir")
    @classmethod
    def _anchor_to_repo(cls, value: Path) -> Path:
        # Relative paths resolve against the repository, so the CLI and the server
        # agree on one data directory whatever directory they are started from.
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    @property
    def clio_api_url(self) -> str:
        return f"{self.clio_base_url}/api/v4"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def pages_dir(self) -> Path:
        return self.data_dir / "pages"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def llm_endpoint(self) -> str:
        if self.llm_base_url:
            return self.llm_base_url.rstrip("/")
        if self.llm_provider == "openai":
            return "https://api.openai.com/v1"
        if self.llm_provider == "gemini":
            return "https://generativelanguage.googleapis.com/v1beta"
        return "https://api.anthropic.com/v1"

    @property
    def clio_configured(self) -> bool:
        return bool(self.clio_client_id and self.clio_client_secret)

    @property
    def models_configured(self) -> bool:
        return bool(self.llm_api_key and self.extract_model and self.merge_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
