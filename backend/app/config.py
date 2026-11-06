from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: str = "data/metacritic.db"
    batch_size: int = 20
    sync_interval_hours: int = 1
    request_delay_seconds: float = 1.0
    request_timeout_seconds: float = 30.0
    request_retries: int = 3


settings = Settings()
