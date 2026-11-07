from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: str = "data/metacritic.db"
    crawl_budget: int = 250  # games the crawl loads per run: new ones and revisits together
    analysis_budget: int = 40  # games the analysis works on per run
    discovery_depth: int = 250  # how many of the newest games the lists are searched for new ones
    young_days: int = 30  # a game is young this long after we found it
    revisit_young_hours: int = 24
    revisit_old_days: int = 7
    crawl_interval_hours: int = 1
    analysis_interval_hours: int = 1
    analysis_offset_minutes: int = 30  # the analysis starts this long after the crawl
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
