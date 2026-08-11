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
    # gpt-5 (reasoning): iterative search + verification, and web_search
    # tool calls cost $10/1k vs $25/1k on gpt-4o. Slower (~40-90s) but
    # more accurate — the frontend's loading overlay covers the wait.
    openai_search_model: str = "gpt-5"
    # Reasoning effort for gpt-5/o-series: low keeps the iterative
    # search-and-verify behaviour but cuts thinking time from minutes
    # to tens of seconds. Raise to "medium" only if result quality dips.
    openai_reasoning_effort: str = "low"
    openai_timeout_seconds: int = 240
    # Small/cheap model for the live ICP-form parse (role+industry chips).
    # No web search — one tiny JSON completion per debounced form edit.
    # gpt-4.1-nano: no reasoning pass, sub-second replies, ~$0.10/M input
    # — the chips must feel instant, this is a UI hint not the search.
    openai_parse_model: str = "gpt-4.1-nano"

    # ── Storage (optional — Neon Postgres). Unset = nothing stored. ─
    database_url: str = ""

    # ── Upstash Redis (optional). Unset = no cache, no rate limit. ──
    redis_url: str = ""
    search_cache_ttl_seconds: int = 86400   # identical ICP → reuse result 24h
    search_daily_limit: int = 3             # searches per device AND per IP per UTC day (0 = off)

    # ── Email report (Resend) ─────────────────────────────────────
    resend_api_key: str = ""
    resend_from_email: str = "kirubakaran.p@leadstrategus.com"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
