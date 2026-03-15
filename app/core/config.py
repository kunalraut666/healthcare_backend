# app/core/config.py
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
DATABASE_URL = os.getenv("DATABASE_URL")

HF_LLM_MODEL = os.getenv("HF_LLM_MODEL", "google/gemma-2-2b-it")
MAX_NEW_TOKENS = int(os.getenv("LLM_MAX_NEW_TOKENS", "384"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
JWT_SECRET: str = "change-me"
JWT_REFRESH_SECRET: str = "change-me-too"
JWT_ALG: str = "HS256"
ACCESS_EXPIRE_MINUTES: int = 15
REFRESH_EXPIRE_DAYS: int = 30

# --- IMPORTANT: make upload dir absolute relative to project root ---
# app/core/config.py  ->  .../app/core/
_THIS_FILE = os.path.abspath(__file__)
_PROJECT_ROOT = os.path.normpath(os.path.join(_THIS_FILE, "..", "..", ".."))  # repo root (healthcare_project_backend)
_DEFAULT_UPLOAD_DIR = os.path.join(_PROJECT_ROOT, "uploads")

class Settings(BaseSettings):
    API_BASE_URL: str = "http://127.0.0.1:8000"      # backend base
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", _DEFAULT_UPLOAD_DIR)

settings = Settings()
