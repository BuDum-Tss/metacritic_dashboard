from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: str = "data/metacritic.db"
    batch_size: int = 20
    sync_interval_hours: int = 1
    sync_run_on_startup: bool = True
    request_delay_seconds: float = 1.0
    request_timeout_seconds: float = 30.0
    request_retries: int = 3

    llm_api_key: str = ""
    llm_base_url: str = "https://ai.starimg.ru"
    llm_model: str = "claude-haiku-5-5"
    llm_timeout_seconds: float = 60.0
    llm_retries: int = 2

    summary_min_interval_hours: int = 24
    critics_sample_limit: int = 30
    users_sample_limit: int = 40
    review_text_limit: int = 600


settings = Settings()
