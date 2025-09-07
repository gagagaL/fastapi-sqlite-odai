import os
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "大喜利お題ジェネレーター"
    database_url: str = "sqlite:///./data/database/app.db"
    debug: bool = True
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
