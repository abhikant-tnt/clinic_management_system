"""
Application configuration settings
"""
import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Get the backend directory (where .env should be created)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

# Auto-create .env file if it doesn't exist
if not ENV_FILE.exists():
    print("Creating .env file with default settings...")
    print("⚠️  IMPORTANT: Please set your PostgreSQL password in the .env file!")
    env_content = """# MongoDB Settings
MONGODB_URL=mongodb://localhost:27017/
MONGODB_DATABASE=patients_database

# PostgreSQL Settings
# IMPORTANT: Set your PostgreSQL password below. Never commit this file to version control!
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=postgres
POSTGRES_PASSWORD=  # REQUIRED: Set your PostgreSQL password here
POSTGRES_DB=clinic_db

# Security Settings (optional)
SECRET_KEY=

# Prisma DATABASE_URL (auto-generated from PostgreSQL settings above)
# DATABASE_URL will be constructed automatically from the settings above
"""
    ENV_FILE.write_text(env_content)
    print(f".env file created at {ENV_FILE}")
    print("⚠️  Please edit .env and set POSTGRES_PASSWORD before running the application!")
else:
    # Update existing .env file with correct port if needed (but never update password)
    try:
        env_content = ENV_FILE.read_text()
        needs_update = False
        
        # Update port if it's still 5432 or 5233 (old values)
        if "POSTGRES_PORT=5432" in env_content or "POSTGRES_PORT=5432\n" in env_content:
            env_content = env_content.replace("POSTGRES_PORT=5432", "POSTGRES_PORT=5433")
            needs_update = True
        elif "POSTGRES_PORT=5233" in env_content or "POSTGRES_PORT=5233\n" in env_content:
            env_content = env_content.replace("POSTGRES_PORT=5233", "POSTGRES_PORT=5433")
            needs_update = True
        
        if needs_update:
            ENV_FILE.write_text(env_content)
            print("Updated .env file with correct PostgreSQL port (5433)")
    except Exception as e:
        print(f"Note: Could not auto-update .env file: {e}")

# Load environment variables from .env file
load_dotenv(ENV_FILE)

class Settings:
    """Application settings"""
    
    # API Settings
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "Clinic Management System"
    VERSION: str = "1.0.0"
    
    # Database Settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "patients_database")
    # PostgreSQL Settings
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5433")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")  # REQUIRED: Must be set in .env file
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "clinic_db")
    
    # Prisma DATABASE_URL (constructed from PostgreSQL settings)
    @property
    def DATABASE_URL(self) -> str:
        """Construct Prisma DATABASE_URL from PostgreSQL settings"""
        if not self.POSTGRES_PASSWORD:
            raise ValueError(
                "POSTGRES_PASSWORD is not set in .env file. "
                "Please set your PostgreSQL password in the .env file before running the application."
            )
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Security Settings
    SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS Settings
    CORS_ORIGINS: list = ["*"]  # Configure for production
    
    class Config:
        case_sensitive = True

settings = Settings()


