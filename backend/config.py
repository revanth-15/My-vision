"""
JARVIS — central configuration.

Every setting is read from environment variables (loaded from backend/.env),
so nothing secret is ever hard-coded and deployment only means setting env vars.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")


def _bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # ---------- Server ----------
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = _bool(os.getenv("FLASK_DEBUG"), True)
    SECRET_KEY = os.getenv("SECRET_KEY", "jarvis-dev-secret-change-me")

    # Comma separated list, or "*" to allow every origin.
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # ---------- Database ----------
    # Default lives outside backend/ so a redeploy of code never wipes data locally.
    DATABASE_PATH = os.getenv(
        "DATABASE_PATH", str(PROJECT_ROOT / "database" / "jarvis.db")
    )

    # ---------- AI provider ----------
    # One of: groq | ollama | together
    AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").strip().lower()

    # Groq (free tier, fastest cloud option)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    # NOTE: llama-3.3-70b-versatile / llama-3.1-8b-instant / mixtral-8x7b-32768
    # were all decommissioned by Groq. gpt-oss-20b is the current fast production
    # model; gpt-oss-120b is the higher-reasoning one.
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    GROQ_BASE_URL = os.getenv(
        "GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions"
    )

    # Ollama (fully local, fully private, no key)
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Together.AI (free tier)
    TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "").strip()
    TOGETHER_MODEL = os.getenv(
        "TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
    )
    TOGETHER_BASE_URL = os.getenv(
        "TOGETHER_BASE_URL", "https://api.together.xyz/v1/chat/completions"
    )

    # ---------- Model behaviour ----------
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "800"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    # How many past turns to replay to the model for context.
    HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "10"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "45"))

    # ---------- Personality ----------
    USER_NAME = os.getenv("USER_NAME", "Sir")
    ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "JARVIS")

    # ---------- Integrations ----------
    DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Frankfurt")
    UNITS = os.getenv("UNITS", "metric")  # metric | imperial
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()  # optional
    NEWS_COUNTRY = os.getenv("NEWS_COUNTRY", "us")

    @classmethod
    def active_model(cls) -> str:
        return {
            "groq": cls.GROQ_MODEL,
            "ollama": cls.OLLAMA_MODEL,
            "together": cls.TOGETHER_MODEL,
        }.get(cls.AI_PROVIDER, cls.GROQ_MODEL)

    @classmethod
    def summary(cls) -> dict:
        """Safe-to-log snapshot. Never includes key values."""
        return {
            "provider": cls.AI_PROVIDER,
            "model": cls.active_model(),
            "database": cls.DATABASE_PATH,
            "debug": cls.DEBUG,
            "groq_key_set": bool(cls.GROQ_API_KEY),
            "together_key_set": bool(cls.TOGETHER_API_KEY),
            "news_key_set": bool(cls.NEWS_API_KEY),
        }
