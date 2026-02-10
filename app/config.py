import os
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "大喜利お題ジェネレーター"
    database_url: str = "sqlite:///./data/database/app.db"
    debug: bool = True

    # AI API設定（第六勢力・第七勢力用）
    gemini_api_key: str = ""
    openai_api_key: str = ""
    ai_provider: str = "gemini"  # "gemini" or "openai"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
