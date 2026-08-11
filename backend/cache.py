"""
backend/cache.py — Upstash Redis: search-result cache + daily rate limit.

Two jobs, both protecting your OpenAI bill:
  1. Cache: identical ICP searches within CACHE TTL reuse the stored
     top-6 result instead of paying for another web search.
  2. Rate limit: N searches per device (or IP fallback) per UTC day.

OPTIONAL: with REDIS_URL unset (or Redis down) both silently no-op —
no caching, no limits, app behaves as before. Upstash gives a
rediss:// URL (TLS) which redis-py handles natively.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from config import get_settings

settings = get_settings()

_client = None
_disabled = False


async def _get_client():
    global _client, _disabled
    if _client is not None or _disabled:
        return _client
    if not settings.redis_url:
        _disabled = True
        logger.info("REDIS_URL not set — no search cache / rate limit")
        return None
    try:
        import redis.asyncio as aioredis
        _client = aioredis.from_url(
            settings.redis_url, decode_responses=True,
            socket_timeout=5, socket_connect_timeout=5,
        )
        await _client.ping()
        logger.info("Redis connected — search cache + rate limit enabled")
    except Exception as e:
        logger.warning(f"Redis unavailable, cache/limits disabled: {e}")
        _client, _disabled = None, True
    return _client


# ── Search-result cache ─────────────────────────────────────────────

def search_cache_key(profile: dict) -> str:
    """Stable key from the fields that actually change the search."""
    basis = {
        # Raw buyer text only — parsed industry/persona lists are no longer
        # sent to GPT (it identifies roles/industries itself), so they must
        # not split the cache either.
        "buyer": (profile.get("buyer_description") or "").strip().lower(),
        "geos":  sorted(x.lower() for x in profile.get("target_geographies") or []),
        "from":  profile.get("date_from") or "",
        "to":    profile.get("date_to") or "",
        "deal":  profile.get("avg_deal_size_category") or "",
    }
    digest = hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()
    return f"search:{digest}"


async def get_cached_search(profile: dict) -> Optional[dict]:
    client = await _get_client()
    if not client:
        return None
    try:
        raw = await client.get(search_cache_key(profile))
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning(f"cache get failed: {e}")
        return None


async def set_cached_search(profile: dict, result: dict) -> None:
    client = await _get_client()
    if not client:
        return
    try:
        await client.set(search_cache_key(profile), json.dumps(result),
                         ex=settings.search_cache_ttl_seconds)
    except Exception as e:
        logger.warning(f"cache set failed: {e}")


# ── Generic small-value cache (ICP parse results etc.) ──────────────

async def get_json(key: str):
    client = await _get_client()
    if not client:
        return None
    try:
        raw = await client.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning(f"cache get_json failed: {e}")
        return None


async def set_json(key: str, value, ttl_seconds: int = 604800) -> None:
    client = await _get_client()
    if not client:
        return
    try:
        await client.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"cache set_json failed: {e}")


# ── Daily rate limit ────────────────────────────────────────────────

_LIMIT_MSG = ("Daily search limit reached ({n}/day). "
              "Try again tomorrow, or contact us for more.")


async def check_rate_limit(device_id: str, ip: str) -> Optional[str]:
    """Returns an error message when over the daily cap, else None.

    Robust dual-key limit: the IP and the device id are counted as
    SEPARATE keys and exceeding EITHER blocks the search — clearing
    localStorage mints a new device id but not a new IP, and rotating
    IPs on one machine still trips the device key. When Redis is
    unreachable the caller falls back to counting today's submissions
    in Postgres (see routes_search), so an outage doesn't disable the
    limit entirely."""
    limit = settings.search_daily_limit
    if limit <= 0:
        return None
    client = await _get_client()
    if not client:
        return "redis_down"          # sentinel: caller uses the DB fallback
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    keys = []
    if ip:
        keys.append(f"rl:{day}:ip:{ip}")
    if device_id:
        keys.append(f"rl:{day}:dev:{device_id}")
    if not keys:
        keys.append(f"rl:{day}:anon")
    try:
        for key in keys:
            n = await client.incr(key)
            if n == 1:
                await client.expire(key, 86400)
            if n > limit:
                return _LIMIT_MSG.format(n=limit)
    except Exception as e:
        logger.warning(f"rate limit check failed: {e}")
        return "redis_down"
    return None
