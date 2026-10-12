from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WAAT_", env_file=".env", extra="ignore")

    data_dir: Path = Path(".waat")
    api_key: SecretStr = Field(default=SecretStr(""), validation_alias="DEEPSEEK_API_KEY")
    model_base_url: str = "https://api.deepseek.com"
    api_model: str = "deepseek-flash"
    required_model: str = "deepseek-v4.1-flash"
    headless: bool = True
    browser_executable: str | None = None
    run_timeout_seconds: float = Field(default=600, gt=0)
    model_timeout_seconds: float = Field(default=60, gt=0)
    action_timeout_ms: int = Field(default=8000, gt=0)
    max_recovery_attempts: int = Field(default=2, ge=0, le=5)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir.resolve() / 'waat.sqlite'}"

    @property
    def key_configured(self) -> bool:
        return bool(self.api_key.get_secret_value().strip())
