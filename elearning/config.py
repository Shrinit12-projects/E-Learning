from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):
    MONGO_URI: str = os.environ.get("MONGO_URI")
    REDIS_URL: str =  os.environ.get("REDIS_URL")
    JWT_SECRET: str = os.environ.get("JWT_SECRET")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 180
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
