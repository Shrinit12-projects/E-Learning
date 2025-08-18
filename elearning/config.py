from pydantic_settings import BaseSettings
from pydantic import Field, validator
from dotenv import load_dotenv
import logging
import sys

load_dotenv()
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Required environment variables
    MONGO_URI: str = Field(..., description="MongoDB connection URI")
    REDIS_URL: str = Field(..., description="Redis connection URL")
    JWT_SECRET: str = Field(..., min_length=32, description="JWT secret key (minimum 32 characters)")
    
    # Optional with defaults
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)
    
    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    
    @validator('JWT_SECRET')
    def validate_jwt_secret(cls, v):
        if len(v) < 32:
            raise ValueError('JWT_SECRET must be at least 32 characters long')
        return v
    
    @validator('MONGO_URI')
    def validate_mongo_uri(cls, v):
        if not v.startswith(('mongodb://', 'mongodb+srv://')):
            raise ValueError('MONGO_URI must be a valid MongoDB connection string')
        return v
    
    @validator('REDIS_URL')
    def validate_redis_url(cls, v):
        if not v.startswith('redis://'):
            raise ValueError('REDIS_URL must be a valid Redis connection string')
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

try:
    settings = Settings()
    logger.info("Configuration loaded successfully")
except Exception as e:
    logger.critical(f"Failed to load configuration: {str(e)}")
    sys.exit(1)
