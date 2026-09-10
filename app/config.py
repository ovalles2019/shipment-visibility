from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/shipments.db"
    api_key: str = "teaching-demo-key"
    delay_check_minutes: int = 5
    notify_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "dispatch@shipvis.local"
    smtp_to: str = "ops@shipvis.local"
    port: int = 8000
    skip_seed: bool = False

    def sqlalchemy_url(self) -> str:
        """Render and many hosts hand out postgres://; SQLAlchemy wants a driver."""
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://") and "+psycopg" not in url:
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


settings = Settings()
