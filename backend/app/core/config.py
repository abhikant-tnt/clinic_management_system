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
    env_content = """# ============================================================
# LOCAL SERVER (Your Clinic's Local Database)
# ============================================================
# This is the PostgreSQL database running on THIS computer
# All patient data is stored here first, then synced to main server
LOCAL_POSTGRES_HOST=localhost
LOCAL_POSTGRES_PORT=5433
LOCAL_POSTGRES_USER=postgres
LOCAL_POSTGRES_PASSWORD=  # REQUIRED: Your LOCAL PostgreSQL password
LOCAL_POSTGRES_DB=clinic_db_local

# ============================================================
# MAIN SERVER (Centralized Database Server)
# ============================================================
# This is the remote PostgreSQL server where data is synced
# Replace 'your-main-server.com' with your actual server IP/domain
MAIN_POSTGRES_HOST=your-main-server.com
MAIN_POSTGRES_PORT=5432
MAIN_POSTGRES_USER=postgres
MAIN_POSTGRES_PASSWORD=  # REQUIRED: Your MAIN SERVER PostgreSQL password
MAIN_POSTGRES_DB=clinic_db_main

# Tenant ID (unique identifier for each clinic)
# ⚠️ IMPORTANT: Each clinic MUST have a unique TENANT_ID!
# Examples: clinic_001, clinic_002, clinic_downtown, clinic_main_street
# Change this to your unique clinic identifier!
TENANT_ID=clinic_001

# Security Settings (optional)
SECRET_KEY=

# Prisma DATABASE_URL (auto-generated from Local PostgreSQL settings above)
# DATABASE_URL will be constructed automatically from the settings above
"""
    ENV_FILE.write_text(env_content, encoding='utf-8')
    print(f".env file created at {ENV_FILE}")
    print("⚠️  Please edit .env and set:")
    print("    - LOCAL_POSTGRES_PASSWORD (your local PostgreSQL password)")
    print("    - MAIN_POSTGRES_PASSWORD (your main server PostgreSQL password)")
    print("    - TENANT_ID (your unique clinic identifier - MUST be unique per clinic!)")
else:
    # Update existing .env file with correct port if needed (but never update password)
    try:
        env_content = ENV_FILE.read_text(encoding='utf-8')
        needs_update = False
        
        # Update old single PostgreSQL settings if present
        if "POSTGRES_HOST=" in env_content and "LOCAL_POSTGRES_HOST" not in env_content:
            needs_update = True
        
        if needs_update:
            ENV_FILE.write_text(env_content, encoding='utf-8')
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
    # ⚠️ Each clinic MUST have a unique TENANT_ID in their .env file!
    # The default "clinic_001" is just a placeholder - change it to your unique clinic ID
    TENANT_ID: str = os.getenv("TENANT_ID", "clinic_001")
    
    # Prisma DATABASE_URL (constructed from Local PostgreSQL settings)
    @property
    def DATABASE_URL(self) -> str:
        if not self.LOCAL_POSTGRES_PASSWORD:   #Construct Prisma DATABASE_URL from Local PostgreSQL settings
            raise ValueError(
                "LOCAL_POSTGRES_PASSWORD is not set in .env file. Please set your Local PostgreSQL password in the .env file before running the application."
            )
        return f"postgresql://{self.LOCAL_POSTGRES_USER}:{self.LOCAL_POSTGRES_PASSWORD}@{self.LOCAL_POSTGRES_HOST}:{self.LOCAL_POSTGRES_PORT}/{self.LOCAL_POSTGRES_DB}"
    
    @property
    def MAIN_DATABASE_URL(self) -> str:
        if not self.MAIN_POSTGRES_PASSWORD: #Construct Main Server DATABASE_URL
            raise ValueError(
                "MAIN_POSTGRES_PASSWORD is not set in .env file.Please set your Main Server PostgreSQL password in the .env file."
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

# Validate TENANT_ID on startup
if settings.TENANT_ID == "clinic_001":
    import warnings
    warnings.warn(
        "⚠️  WARNING: Using default TENANT_ID 'clinic_001'. "
        "Please set a unique TENANT_ID in your .env file for this clinic! "
        "Each clinic must have a different TENANT_ID to keep data separate.",
        UserWarning
    )


