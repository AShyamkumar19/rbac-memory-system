from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """
    Application settings using Pydantic BaseSettings.
    This automatically loads from environment variables or .env file.
    """
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://rbac_user:rbac_password@localhost:5432/rbac_memory_db"
    REDIS_URL: str = "redis://localhost:6379"
    
    # Security Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    
    # CORS Settings (for frontend integration)
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",  # React development server
        "http://localhost:8080",  # Vue development server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080"
    ]
    
    # Application Settings
    APP_NAME: str = "RBAC Memory Management System"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Cache TTL Settings (Time To Live in seconds)
    PERMISSION_CACHE_TTL: int = 3600      # 1 hour
    SESSION_CACHE_TTL: int = 28800        # 8 hours
    QUERY_CACHE_TTL: int = 300            # 5 minutes
    
    # Memory Settings
    SHORT_TERM_MEMORY_TTL: int = 86400    # 24 hours
    MID_TERM_MEMORY_TTL: int = 7776000    # 90 days
    LONG_TERM_MEMORY_TTL: int = 220752000 # 7 years
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100
    
    # Security
    MIN_PASSWORD_LENGTH: int = 8
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_DURATION: int = 1800  # 30 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  

# Create global settings instance
settings = Settings()

# Validate critical settings
def validate_settings():
    """Validate critical settings on startup"""
    if settings.SECRET_KEY == os.getenv("SECRET_KEY"):
        if not settings.DEBUG:
            raise ValueError("SECRET_KEY must be changed in production!")
    
    if not settings.DATABASE_URL:
        raise ValueError("DATABASE_URL is required")
    
    if not settings.REDIS_URL:
        raise ValueError("REDIS_URL is required")

# Run validation
validate_settings()