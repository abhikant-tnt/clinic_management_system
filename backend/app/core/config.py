"""
Application configuration settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Get the backend directory (where .env should be created)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

# Auto-create .env file if it doesn't exist
if not ENV_FILE.exists():
    print("Creating .env file with default settings...")
    print("⚠️  IMPORTANT: Please set your PostgreSQL passwords in the .env file!")
    import secrets
    generated_secret_key = secrets.token_urlsafe(32)
    env_content = f"""# ============================================================
# PostgreSQL Database Server
# ============================================================
# Replace 'your-main-server.com' with your actual server IP/domain
MAIN_POSTGRES_HOST=your-main-server.com
MAIN_POSTGRES_PORT=5432
MAIN_POSTGRES_USER=postgres
MAIN_POSTGRES_PASSWORD=  # REQUIRED: Your PostgreSQL password
MAIN_POSTGRES_DB=clinic_db_main

# Tenant ID (unique identifier for each clinic)
# ⚠️ IMPORTANT: Each clinic MUST have a unique TENANT_ID!
# Examples: clinic_001, clinic_002, clinic_downtown, clinic_main_street
# Change this to your unique clinic identifier!
TENANT_ID=clinic_001

# Security Settings (REQUIRED - auto-generated)
# This key was automatically generated. Keep it secure!
SECRET_KEY={generated_secret_key}

# DATABASE_URL (auto-generated from PostgreSQL settings above)
# DATABASE_URL will be constructed automatically from the settings above
"""
    ENV_FILE.write_text(env_content, encoding='utf-8')
    print(f".env file created at {ENV_FILE}")
    print("⚠️  Please edit .env and set the correct MAIN_POSTGRES_PASSWORD and TENANT_ID (unique per clinic)!")
    print(f"✅ SECRET_KEY has been auto-generated and saved to .env file")
# .env file exists, no action needed

# Load environment variables from .env file
load_dotenv(ENV_FILE)

class Settings:
    """Application settings"""
    
    # API Settings
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "Clinic Management System"
    VERSION: str = "1.0.0"
    
    # PostgreSQL Settings
    MAIN_POSTGRES_HOST: str = os.getenv("MAIN_POSTGRES_HOST", "localhost")
    MAIN_POSTGRES_PORT: str = os.getenv("MAIN_POSTGRES_PORT", "5432")
    MAIN_POSTGRES_USER: str = os.getenv("MAIN_POSTGRES_USER", "postgres")
    MAIN_POSTGRES_PASSWORD: str = os.getenv("MAIN_POSTGRES_PASSWORD", "")  # REQUIRED: Must be set in .env file
    MAIN_POSTGRES_DB: str = os.getenv("MAIN_POSTGRES_DB", "clinic_db_main")
    
    # Tenant ID (unique identifier for each clinic)
    # ⚠️ Each clinic MUST have a unique TENANT_ID in their .env file!
    # The default "clinic_001" is just a placeholder - change it to your unique clinic ID
    TENANT_ID: str = os.getenv("TENANT_ID", "clinic_001")
    
    # DATABASE_URL (constructed from PostgreSQL settings)
    @property
    def DATABASE_URL(self) -> str:
        if not self.MAIN_POSTGRES_PASSWORD:
            raise ValueError(
                "MAIN_POSTGRES_PASSWORD is not set in .env file. Please set your PostgreSQL password in the .env file before running the application."
            )
        return f"postgresql://{self.MAIN_POSTGRES_USER}:{self.MAIN_POSTGRES_PASSWORD}@{self.MAIN_POSTGRES_HOST}:{self.MAIN_POSTGRES_PORT}/{self.MAIN_POSTGRES_DB}"
    
    # Security Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720  # 12 hours
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    # CORS Settings - restrict in production
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",") if os.getenv("CORS_ORIGINS") else ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        case_sensitive = True

settings = Settings()

# Validate and auto-generate SECRET_KEY if missing
if not settings.SECRET_KEY or settings.SECRET_KEY == "" or len(settings.SECRET_KEY) < 32:
    import secrets
    generated_key = secrets.token_urlsafe(32)
    # Update environment variable
    os.environ["SECRET_KEY"] = generated_key
    settings.SECRET_KEY = generated_key
    
    # Try to update .env file if it exists
    if ENV_FILE.exists():
        try:
            env_content = ENV_FILE.read_text(encoding='utf-8')
            # Update SECRET_KEY in .env file
            if "SECRET_KEY=" in env_content:
                import re
                env_content = re.sub(r'SECRET_KEY=.*', f'SECRET_KEY={generated_key}', env_content)
            else:
                env_content += f"\nSECRET_KEY={generated_key}\n"
            ENV_FILE.write_text(env_content, encoding='utf-8')
            print("✅ Auto-generated SECRET_KEY and saved to .env file")
        except Exception as e:
            print(f"⚠️  Warning: Could not update .env file: {e}")
            print(f"⚠️  Please manually add this SECRET_KEY to your .env file: {generated_key}")
    else:
        print("⚠️  Warning: .env file not found. Using generated SECRET_KEY for this session only.")
        print(f"⚠️  Please create .env file and add: SECRET_KEY={generated_key}")

if settings.TENANT_ID == "clinic_001":
    print("WARNING: Using default TENANT_ID 'clinic_001'. Please set a unique TENANT_ID in your .env file.")


