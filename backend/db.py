"""
backend/db.py — thin lead-capture / tracking store (Neon Postgres).

Three tables, written fire-and-forget from the API routes:
  icp_submissions  — raw ICP form payload + email + IP + device/session ids
  search_results   — the top-6 events JSON returned for a submission
  consent_log      — cookie banner / form consent records

Everything here is OPTIONAL: when DATABASE_URL is unset (or asyncpg is
missing / the DB is down) every function silently no-ops, so the app
runs storage-less exactly as before. Never let tracking break a search.
"""
import json
import uuid
from typing import Optional

from loguru import logger

from config import get_settings

settings = get_settings()

_pool = None          # asyncpg.Pool | None
_disabled = False     # set True after a fatal init failure — stop retrying


def _normalise_dsn(url: str) -> str:
    # Neon/Render give postgres:// or postgresql:// with ?sslmode=require —
    # asyncpg accepts both scheme spellings and the sslmode query param.
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _get_pool():
    global _pool, _disabled
    if _pool is not None or _disabled:
        return _pool
    if not settings.database_url:
        _disabled = True
        logger.info("DATABASE_URL not set — submissions/results are not stored")
        return None
    try:
        import asyncpg
        _pool = await asyncpg.create_pool(
            _normalise_dsn(settings.database_url), min_size=0, max_size=3,
            command_timeout=15,
        )
        await _init_tables(_pool)
        logger.info("DB connected — lead/tracking storage enabled")
    except Exception as e:
        logger.warning(f"DB unavailable, storage disabled: {e}")
        _pool, _disabled = None, True
    return _pool


async def _init_tables(pool) -> None:
    async with pool.acquire() as con:
        await con.execute("""
        CREATE TABLE IF NOT EXISTS icp_submissions (
            id           UUID PRIMARY KEY,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            email        TEXT,
            company_name TEXT,
            buyer_description TEXT,
            profile      JSONB,
            ip_address   TEXT,
            device_id    TEXT,
            session_id   TEXT,
            from_cache   BOOLEAN DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS search_results (
            id            UUID PRIMARY KEY,
            submission_id UUID REFERENCES icp_submissions(id) ON DELETE CASCADE,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            event_count   INT,
            events        JSONB,
            search_notes  TEXT
        );
        CREATE TABLE IF NOT EXISTS consent_log (
            id           UUID PRIMARY KEY,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            consent_type TEXT,
            accepted     BOOLEAN,
            categories   JSONB,
            ip_address   TEXT,
            session_id   TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_subs_created ON icp_submissions (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_subs_email   ON icp_submissions (email);
        """)


async def log_submission(profile: dict, ip: str, device_id: str,
                         session_id: str, from_cache: bool) -> Optional[str]:
    """Store the raw ICP submission; returns submission id (or None)."""
    pool = await _get_pool()
    if not pool:
        return None
    sub_id = str(uuid.uuid4())
    try:
        async with pool.acquire() as con:
            await con.execute(
                """INSERT INTO icp_submissions
                   (id, email, company_name, buyer_description, profile,
                    ip_address, device_id, session_id, from_cache)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                sub_id,
                profile.get("email") or "",
                profile.get("company_name") or "",
                profile.get("buyer_description") or "",
                json.dumps(profile),
                ip, device_id, session_id, from_cache,
            )
        return sub_id
    except Exception as e:
        logger.warning(f"log_submission failed: {e}")
        return None


async def log_search_result(submission_id: Optional[str], result: dict) -> None:
    pool = await _get_pool()
    if not pool or not submission_id:
        return
    try:
        async with pool.acquire() as con:
            await con.execute(
                """INSERT INTO search_results
                   (id, submission_id, event_count, events, search_notes)
                   VALUES ($1,$2,$3,$4,$5)""",
                str(uuid.uuid4()), submission_id,
                len(result.get("events") or []),
                json.dumps(result.get("events") or []),
                result.get("search_notes") or "",
            )
    except Exception as e:
        logger.warning(f"log_search_result failed: {e}")


async def log_consent(consent_type: str, accepted: bool, categories: list,
                      ip: str, session_id: str) -> None:
    pool = await _get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as con:
            await con.execute(
                """INSERT INTO consent_log
                   (id, consent_type, accepted, categories, ip_address, session_id)
                   VALUES ($1,$2,$3,$4,$5,$6)""",
                str(uuid.uuid4()), consent_type, accepted,
                json.dumps(categories or []), ip, session_id,
            )
    except Exception as e:
        logger.warning(f"log_consent failed: {e}")
