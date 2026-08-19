"""
backend/db.py - thin lead-capture / tracking store (Neon Postgres).

Three tables, written fire-and-forget from the API routes:
  icp_submissions  - raw ICP form payload + email + IP + device/session ids
  search_results   - the top-6 events JSON returned for a submission
  consent_log      - cookie banner / form consent records

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
_disabled = False     # set True after a fatal init failure - stop retrying


def _normalise_dsn(url: str) -> str:
    # Neon/Render give postgres:// or postgresql:// with ?sslmode=require -
    # asyncpg accepts both scheme spellings and the sslmode query param.
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _get_pool():
    global _pool, _disabled
    if _pool is not None or _disabled:
        return _pool
    if not settings.database_url:
        _disabled = True
        logger.info("DATABASE_URL not set - submissions/results are not stored")
        return None
    try:
        import asyncpg
        _pool = await asyncpg.create_pool(
            _normalise_dsn(settings.database_url), min_size=0, max_size=3,
            command_timeout=15,
        )
        await _init_tables(_pool)
        logger.info("DB connected - lead/tracking storage enabled")
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
        CREATE TABLE IF NOT EXISTS sessions (
            session_id   TEXT PRIMARY KEY,
            first_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen    TIMESTAMPTZ NOT NULL DEFAULT now(),
            referrer     TEXT,
            landing_page TEXT,
            ip_address   TEXT,
            user_agent   TEXT,
            total_time_seconds INT NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS activity_events (
            id            UUID PRIMARY KEY,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            session_id    TEXT,
            event_type    TEXT,
            submission_id TEXT,
            event_id      TEXT,
            metadata      JSONB,
            ip_address    TEXT
        );
        CREATE TABLE IF NOT EXISTS email_reports (
            id          UUID PRIMARY KEY,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            email       TEXT,
            event_count INT,
            company_name TEXT,
            session_id  TEXT,
            ip_address  TEXT,
            success     BOOLEAN
        );
        CREATE TABLE IF NOT EXISTS email_verifications (
            id          UUID PRIMARY KEY,
            email       TEXT NOT NULL,
            code_hash   TEXT NOT NULL,
            ip_address  TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at  TIMESTAMPTZ NOT NULL,
            attempts    INT NOT NULL DEFAULT 0,
            verified_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_ver_email ON email_verifications (email, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_subs_created ON icp_submissions (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_subs_email   ON icp_submissions (email);
        CREATE INDEX IF NOT EXISTS idx_act_session  ON activity_events (session_id, created_at DESC);
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


async def upsert_session(session_id: str, referrer: str, landing_page: str,
                         ip: str, user_agent: str) -> None:
    pool = await _get_pool()
    if not pool or not session_id:
        return
    try:
        async with pool.acquire() as con:
            await con.execute(
                """INSERT INTO sessions (session_id, referrer, landing_page, ip_address, user_agent)
                   VALUES ($1,$2,$3,$4,$5)
                   ON CONFLICT (session_id) DO UPDATE SET last_seen = now()""",
                session_id, referrer, landing_page, ip, user_agent,
            )
    except Exception as e:
        logger.warning(f"upsert_session failed: {e}")


async def session_heartbeat(session_id: str, delta_seconds: int) -> None:
    pool = await _get_pool()
    if not pool or not session_id:
        return
    try:
        async with pool.acquire() as con:
            await con.execute(
                """UPDATE sessions SET last_seen = now(),
                       total_time_seconds = total_time_seconds + $2
                   WHERE session_id = $1""",
                session_id, max(0, int(delta_seconds or 0)),
            )
    except Exception as e:
        logger.warning(f"session_heartbeat failed: {e}")


async def log_activity(session_id: str, event_type: str, submission_id: str,
                       event_id: str, metadata: dict, ip: str) -> None:
    pool = await _get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as con:
            await con.execute(
                """INSERT INTO activity_events
                   (id, session_id, event_type, submission_id, event_id, metadata, ip_address)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                str(uuid.uuid4()), session_id, event_type,
                submission_id or "", event_id or "",
                json.dumps(metadata or {}), ip,
            )
    except Exception as e:
        logger.warning(f"log_activity failed: {e}")


async def log_email_report(email: str, event_count: int, company_name: str,
                           session_id: str, ip: str, success: bool) -> None:
    pool = await _get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as con:
            await con.execute(
                """INSERT INTO email_reports
                   (id, email, event_count, company_name, session_id, ip_address, success)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                str(uuid.uuid4()), email, event_count, company_name,
                session_id, ip, success,
            )
    except Exception as e:
        logger.warning(f"log_email_report failed: {e}")


async def count_searches_today(ip: str, device_id: str) -> int:
    """Rate-limit fallback when Redis is unreachable: how many searches
    this IP OR device has already made since UTC midnight. Returns 0
    when the DB is also unavailable (both layers down → fail open)."""
    pool = await _get_pool()
    if not pool:
        return 0
    try:
        async with pool.acquire() as con:
            row = await con.fetchrow(
                """SELECT count(*) AS n FROM icp_submissions
                   WHERE created_at >= date_trunc('day', now() AT TIME ZONE 'utc')
                     AND ((ip_address <> '' AND ip_address = $1)
                          OR (device_id <> '' AND device_id = $2))""",
                ip or "", device_id or "",
            )
            return int(row["n"] or 0)
    except Exception as e:
        logger.warning(f"count_searches_today failed: {e}")
        return 0


# ── Email OTP verification ──────────────────────────────────────────

async def create_verification(email: str, code_hash: str, ip: str,
                              ttl_minutes: int = 10) -> bool:
    """Store a new OTP for this email (invalidates older pending ones).
    Returns False when storage is unavailable (caller fails open)."""
    pool = await _get_pool()
    if not pool:
        return False
    try:
        async with pool.acquire() as con:
            await con.execute(
                "DELETE FROM email_verifications WHERE email = $1 AND verified_at IS NULL",
                email.lower())
            await con.execute(
                """INSERT INTO email_verifications (id, email, code_hash, ip_address, expires_at)
                   VALUES ($1,$2,$3,$4, now() + ($5 || ' minutes')::interval)""",
                str(uuid.uuid4()), email.lower(), code_hash, ip, str(ttl_minutes))
        return True
    except Exception as e:
        logger.warning(f"create_verification failed: {e}")
        return False


async def sends_in_last_hour(email: str, ip: str) -> int:
    pool = await _get_pool()
    if not pool:
        return 0
    try:
        async with pool.acquire() as con:
            row = await con.fetchrow(
                """SELECT count(*) AS n FROM email_verifications
                   WHERE created_at > now() - interval '1 hour'
                     AND (email = $1 OR (ip_address <> '' AND ip_address = $2))""",
                email.lower(), ip or "")
            return int(row["n"] or 0)
    except Exception as e:
        logger.warning(f"sends_in_last_hour failed: {e}")
        return 0


async def check_verification_code(email: str, code_hash: str,
                                  max_attempts: int = 5) -> str:
    """Returns 'ok', 'wrong', 'expired', or 'unavailable'.
    Counts attempts so the 6-digit space can't be brute-forced."""
    pool = await _get_pool()
    if not pool:
        return "unavailable"
    try:
        async with pool.acquire() as con:
            row = await con.fetchrow(
                """SELECT id, code_hash, attempts, expires_at < now() AS expired
                   FROM email_verifications
                   WHERE email = $1 AND verified_at IS NULL
                   ORDER BY created_at DESC LIMIT 1""",
                email.lower())
            if not row or row["expired"] or row["attempts"] >= max_attempts:
                return "expired"
            if row["code_hash"] != code_hash:
                await con.execute(
                    "UPDATE email_verifications SET attempts = attempts + 1 WHERE id = $1",
                    row["id"])
                return "wrong"
            await con.execute(
                "UPDATE email_verifications SET verified_at = now() WHERE id = $1",
                row["id"])
        return "ok"
    except Exception as e:
        logger.warning(f"check_verification_code failed: {e}")
        return "unavailable"


async def is_email_verified(email: str, within_days: int = 30) -> Optional[bool]:
    """True/False, or None when storage is unavailable (fail open)."""
    pool = await _get_pool()
    if not pool:
        return None
    try:
        async with pool.acquire() as con:
            row = await con.fetchrow(
                """SELECT 1 FROM email_verifications
                   WHERE email = $1 AND verified_at > now() - ($2 || ' days')::interval
                   LIMIT 1""",
                email.lower(), str(within_days))
            return row is not None
    except Exception as e:
        logger.warning(f"is_email_verified failed: {e}")
        return None


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
