"""
backend/cache.py - Upstash Redis: search-result cache + daily rate limit.

Two jobs, both protecting your OpenAI bill:
  1. Cache: identical ICP searches within CACHE TTL reuse the stored
     top-6 result instead of paying for another web search.
  2. Rate limit: N searches per device (or IP fallback) per UTC day.

OPTIONAL: with REDIS_URL unset (or Redis down) both silently no-op -
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
        logger.info("REDIS_URL not set - no search cache / rate limit")
        return None
    try:
        import redis.asyncio as aioredis
        _client = aioredis.from_url(
            settings.redis_url, decode_responses=True,
            socket_timeout=5, socket_connect_timeout=5,
        )
        await _client.ping()
        logger.info("Redis connected - search cache + rate limit enabled")
    except Exception as e:
        logger.warning(f"Redis unavailable, cache/limits disabled: {e}")
        _client, _disabled = None, True
    return _client


# ── Search-result cache ─────────────────────────────────────────────

def search_cache_key(profile: dict) -> str:
    """Stable key from the fields that actually change the search."""
    basis = {
        # Raw buyer text only - parsed industry/persona lists are no longer
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

# The cap counts the network as well as the browser, so colleagues
# behind one office IP share it - say so, otherwise "you've used 3"
# reads as a bug to someone on their first search of the day.
_LIMIT_MSG = ("Daily search limit reached ({n}/day, counted per browser "
              "and per network). Try again tomorrow, or contact us for more.")


def limit_message(n: int) -> str:
    """The one wording for "you're out of searches", shared with the
    Postgres fallback path in routes_search."""
    return _LIMIT_MSG.format(n=n)


def _limit_keys(device_id: str, ip: str) -> list:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    keys = []
    if ip:
        keys.append(f"rl:{day}:ip:{ip}")
    if device_id:
        keys.append(f"rl:{day}:dev:{device_id}")
    return keys or [f"rl:{day}:anon"]


async def check_rate_limit(device_id: str, ip: str) -> Optional[str]:
    """Returns an error message when over the daily cap, else None.

    Robust dual-key limit: the IP and the device id are counted as
    SEPARATE keys and exceeding EITHER blocks the search - clearing
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
    try:
        counted = []
        for key in _limit_keys(device_id, ip):
            n = await client.incr(key)
            if n == 1:
                await client.expire(key, 86400)
            counted.append(key)
            if n > limit:
                # Hand back everything this blocked attempt counted -
                # otherwise retrying against a limit that already said
                # no keeps inflating the counter past it, and a later
                # legitimate refund can never catch up.
                for k in counted:
                    await client.decr(k)
                return _LIMIT_MSG.format(n=limit)
    except Exception as e:
        logger.warning(f"rate limit check failed: {e}")
        return "redis_down"
    return None


async def refund_rate_limit(device_id: str, ip: str) -> None:
    """Give back a slot counted by check_rate_limit for a search that
    never actually ran - a cache hit (costs nothing) or a search that
    failed. Without this a user burns their 3/day on results they were
    handed from cache or on our own errors. Floors at 0 so a stray
    refund can't mint free searches."""
    if settings.search_daily_limit <= 0:
        return
    client = await _get_client()
    if not client:
        return
    try:
        for key in _limit_keys(device_id, ip):
            if await client.decr(key) < 0:
                await client.set(key, 0, ex=86400)
    except Exception as e:
        logger.warning(f"rate limit refund failed: {e}")
