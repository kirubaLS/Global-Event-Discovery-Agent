"""
backend/config.py — slim settings for the GPT-web-search backend.

Only three concerns remain server-side:
  1. /api/search        → OpenAI web search (gpt_search.py)
  2. /api/email-report  → PDF report via Resend (api/routes_email.py)
  3. maintenance switch → main.py middleware
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Event Intelligence Agent"
    debug: bool = False
    frontend_origin: str = "http://localhost:5173"

    # Site-wide kill switch (frontend checks /api/maintenance-status)
    maintenance_mode: bool = False
    maintenance_message: str = ""

    # ── OpenAI (ChatGPT with real web search) ─────────────────────
    openai_api_key: str = ""
    # Must be a model that supports the Responses API `web_search` tool.
    openai_search_model: str = "gpt-4o"
    openai_timeout_seconds: int = 180

    # ── Storage (optional — Neon Postgres). Unset = nothing stored. ─
    database_url: str = ""

    # ── Upstash Redis (optional). Unset = no cache, no rate limit. ──
    redis_url: str = ""
    search_cache_ttl_seconds: int = 86400   # identical ICP → reuse result 24h
    search_daily_limit: int = 10            # searches per device/IP per UTC day (0 = off)

    # ── Email report (Resend) ─────────────────────────────────────
    resend_api_key: str = ""
    resend_from_email: str = "kirubakaran.p@leadstrategus.com"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
