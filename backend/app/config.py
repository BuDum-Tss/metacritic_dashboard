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

    youtube_api_key: str = ""
    videos_budget: int = 4  # games the video search works on per run
    videos_interval_hours: int = 1
    videos_offset_minutes: int = 45  # the video search starts this long after the crawl
    videos_refresh_days: int = 14  # a found video of a young game is searched again after this long
    videos_retry_days: int = 3  # a young game without a video is searched again after this long
    videos_results: int = 15  # search results looked at per query

    openrouter_api_key: str = ""  # speech recognition of the videos without subtitles
    stt_model: str = "openai/whisper-large-v3"
    stt_chunk_minutes: int = 10  # the sound is cut into pieces of this length (a request takes up to 25 MB)
    stt_max_video_minutes: int = 600  # longer videos are not recognised: too expensive
    stt_budget_minutes: int = 600  # sound recognised per request of the user at most
    stt_timeout_seconds: float = 120.0
    transcript_max_playlist_videos: int = 50

    video_summary_chunk_chars: int = 24000  # the transcript goes to the model in windows of this size
    video_summary_moments_per_chunk: int = 10
    video_summary_max_moments: int = 80

    summary_min_interval_hours: int = 24
    critics_sample_limit: int = 30
    users_sample_limit: int = 40
    review_text_limit: int = 600


settings = Settings()
