import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find .env: check backend/ first, then project root (parent dir)
_BACKEND_DIR = Path(__file__).parent
_ENV_CANDIDATES = [
    _BACKEND_DIR / ".env",           # backend/.env
    _BACKEND_DIR.parent / ".env",    # gitwi/.env  (project root)
]
_ENV_FILE = next((str(p) for p in _ENV_CANDIDATES if p.exists()), ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Groq API — free at console.groq.com
    GROQ_API_KEY: str = ""

    # Optional GitHub token for higher clone rate limits
    GITHUB_TOKEN: str = ""

    # Local storage paths
    REPOS_DIR: str = str(Path.home() / ".gitwi" / "repos")
    CHROMA_DIR: str = str(Path.home() / ".gitwi" / "chroma")

    # Model settings
    CHAT_MODEL: str = "llama-3.1-8b-instant"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # RAG settings
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    TOP_K_RETRIEVAL: int = 8

    # Server
    PORT: int = 8001
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()

# Ensure local dirs exist
os.makedirs(settings.REPOS_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_DIR, exist_ok=True)
