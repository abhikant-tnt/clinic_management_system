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
    print("⚠️  IMPORTANT: Please set your PostgreSQL passwords in the .env file!")
    env_content = """# Local PostgreSQL Settings (for each clinic)
# IMPORTANT: Set your Local PostgreSQL password below. Never commit this file to version control!
LOCAL_POSTGRES_HOST=localhost
LOCAL_POSTGRES_PORT=5433
LOCAL_POSTGRES_USER=postgres
LOCAL_POSTGRES_PASSWORD=  # REQUIRED: Set your Local PostgreSQL password here
LOCAL_POSTGRES_DB=clinic_db_local

# Main Server PostgreSQL Settings (centralized server)
# IMPORTANT: Set your Main Server PostgreSQL password below. Never commit this file to version control!
MAIN_POSTGRES_HOST=your-main-server.com
MAIN_POSTGRES_PORT=5432
MAIN_POSTGRES_USER=postgres
MAIN_POSTGRES_PASSWORD=  # REQUIRED: Set your Main Server PostgreSQL password here
MAIN_POSTGRES_DB=clinic_db_main

# Tenant ID (unique identifier for each clinic)
TENANT_ID=clinic_001

# Security Settings (optional)
SECRET_KEY=

# Prisma DATABASE_URL (auto-generated from Local PostgreSQL settings above)
# DATABASE_URL will be constructed automatically from the settings above
"""
    ENV_FILE.write_text(env_content)
    print(f".env file created at {ENV_FILE}")
    print("⚠️  Please edit .env and set LOCAL_POSTGRES_PASSWORD, MAIN_POSTGRES_PASSWORD, and TENANT_ID before running the application!")
else:
    # Update existing .env file with correct port if needed (but never update password)
    try:
        env_content = ENV_FILE.read_text()
        needs_update = False
        
        # Update old MongoDB and single PostgreSQL settings if present
        if "MONGODB_URL" in env_content:
            needs_update = True
        if "POSTGRES_HOST=" in env_content and "LOCAL_POSTGRES_HOST" not in env_content:
            needs_update = True
        
        if needs_update:
            ENV_FILE.write_text(env_content)
            print("Updated .env file with correct PostgreSQL port (5433)")
    except (OSError, PermissionError, IOError) as e:  # pylint: disable=broad-except
        print(f"Note: Could not auto-update .env file: {e}")

# Load environment variables from .env file
load_dotenv(ENV_FILE)

class Settings:
    """Application settings"""
    
    # API Settings
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "Clinic Management System"
    VERSION: str = "1.0.0"
    
    # Local PostgreSQL Settings (for each clinic)
    LOCAL_POSTGRES_HOST: str = os.getenv("LOCAL_POSTGRES_HOST", "localhost")
    LOCAL_POSTGRES_PORT: str = os.getenv("LOCAL_POSTGRES_PORT", "5433")
    LOCAL_POSTGRES_USER: str = os.getenv("LOCAL_POSTGRES_USER", "postgres")
    LOCAL_POSTGRES_PASSWORD: str = os.getenv("LOCAL_POSTGRES_PASSWORD", "")  # REQUIRED: Must be set in .env file
    LOCAL_POSTGRES_DB: str = os.getenv("LOCAL_POSTGRES_DB", "clinic_db_local")
    
    # Main Server PostgreSQL Settings (centralized)
    MAIN_POSTGRES_HOST: str = os.getenv("MAIN_POSTGRES_HOST", "localhost")
    MAIN_POSTGRES_PORT: str = os.getenv("MAIN_POSTGRES_PORT", "5432")
    MAIN_POSTGRES_USER: str = os.getenv("MAIN_POSTGRES_USER", "postgres")
    MAIN_POSTGRES_PASSWORD: str = os.getenv("MAIN_POSTGRES_PASSWORD", "")  # REQUIRED: Must be set in .env file
    MAIN_POSTGRES_DB: str = os.getenv("MAIN_POSTGRES_DB", "clinic_db_main")
    
    # Tenant ID (unique identifier for each clinic)
    TENANT_ID: str = os.getenv("TENANT_ID", "clinic_001")
    
    # Prisma DATABASE_URL (constructed from Local PostgreSQL settings)
    @property
    def DATABASE_URL(self) -> str:
        """Construct Prisma DATABASE_URL from Local PostgreSQL settings"""
        if not self.LOCAL_POSTGRES_PASSWORD:
            raise ValueError(
                "LOCAL_POSTGRES_PASSWORD is not set in .env file. "
                "Please set your Local PostgreSQL password in the .env file before running the application."
            )
        return f"postgresql://{self.LOCAL_POSTGRES_USER}:{self.LOCAL_POSTGRES_PASSWORD}@{self.LOCAL_POSTGRES_HOST}:{self.LOCAL_POSTGRES_PORT}/{self.LOCAL_POSTGRES_DB}"
    
    @property
    def MAIN_DATABASE_URL(self) -> str:
        """Construct Main Server DATABASE_URL"""
        if not self.MAIN_POSTGRES_PASSWORD:
            raise ValueError(
                "MAIN_POSTGRES_PASSWORD is not set in .env file. "
                "Please set your Main Server PostgreSQL password in the .env file."
            )
        return f"postgresql://{self.MAIN_POSTGRES_USER}:{self.MAIN_POSTGRES_PASSWORD}@{self.MAIN_POSTGRES_HOST}:{self.MAIN_POSTGRES_PORT}/{self.MAIN_POSTGRES_DB}"
    
    # Security Settings
    SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS Settings
    CORS_ORIGINS: list = ["*"]  # Configure for production
    
    class Config:
        case_sensitive = True

settings = Settings()


