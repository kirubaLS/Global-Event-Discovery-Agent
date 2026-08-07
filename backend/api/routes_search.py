"""
backend/api/routes_search.py — /api/search via ChatGPT web search,
plus tiny stubs for the endpoints the (unchanged) frontend still calls.

The old pipeline (DB, scrapers, embeddings, queue, analytics, consent)
is gone. Every stub returns the safe "empty" shape its caller already
handles gracefully — see frontend/src/api/client.js.
"""
from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

import cache
import db
from config import get_settings
from gpt_search import run_gpt_event_search

router = APIRouter()
settings = get_settings()


def _client_ip(request: Request) -> str:
    # Render sits behind a proxy — real client IP is the first entry
    # in X-Forwarded-For; request.client is the proxy otherwise.
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


class SearchRequest(BaseModel):
    profile: dict
    captcha_token: str = ""
    honeypot: str = ""
    consent: bool = False


@router.post("/search")
async def search(req: SearchRequest, request: Request):
    if req.honeypot:                       # bots fill the hidden field
        raise HTTPException(status_code=400, detail="Invalid submission.")
    if not (req.profile.get("buyer_description") or req.profile.get("target_industries")):
        raise HTTPException(status_code=422, detail="Describe your buyer first.")

    ip         = _client_ip(request)
    device_id  = request.headers.get("x-device-id", "")
    session_id = request.headers.get("x-session-id", "")

    # Daily cap (Upstash Redis; fails open when unset/down)
    limit_msg = await cache.check_rate_limit(device_id, ip)
    if limit_msg:
        raise HTTPException(status_code=429, detail=limit_msg)

    # Cache: identical ICP within TTL → skip the OpenAI call entirely
    result = await cache.get_cached_search(req.profile)
    from_cache = result is not None
    if not from_cache:
        try:
            result = await run_gpt_event_search(req.profile)
        except RuntimeError as e:          # missing API key → clear 503
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error(f"GPT event search failed: {e}")
            raise HTTPException(status_code=500, detail="Search failed - please try again.")
        if result.get("events"):
            await cache.set_cached_search(req.profile, result)

    # Lead capture (Neon Postgres; no-ops when DATABASE_URL unset)
    sub_id = await db.log_submission(req.profile, ip, device_id, session_id, from_cache)
    await db.log_search_result(sub_id, result)

    # Same envelope the old queue-less inline path used (App.jsx branches on it)
    return {"status": "done", "job_id": None, "result": result}


# ── Maintenance + stats ─────────────────────────────────────────────

@router.get("/maintenance-status")
async def maintenance_status():
    return {"maintenance": settings.maintenance_mode,
            "message": settings.maintenance_message}


@router.get("/stats")
async def stats():
    # Static marketing-level numbers; the event DB no longer exists.
    return {
        "total_events_in_db": 11000,
        "countries_covered": 90,
        "live_sources": 1,
        "top_event_names": [],
        "resend_enabled": bool(settings.resend_api_key),
    }


# ── Form-helper stubs (frontend falls back to its local logic) ──────

class ParseIcpRequest(BaseModel):
    text: str = ""


@router.post("/parse-icp")
async def parse_icp(_: ParseIcpRequest):
    return {"source": "rules"}             # keep ICPForm's local keyword parse


@router.get("/geo-list")
async def geo_list():
    return {"countries": []}               # ICPForm falls back to GEO_OPTIONS


@router.get("/geo-hint")
async def geo_hint():
    return {}


@router.get("/city-hint")
async def city_hint():
    return {"exact_match": True, "suggestions": []}


# ── Analytics / consent no-ops (calls are fire-and-forget) ──────────

@router.post("/analytics/session/start")
async def analytics_session_start(_: dict = None):
    return {"ok": True}


@router.post("/analytics/session/heartbeat")
async def analytics_heartbeat(_: dict = None):
    return {"ok": True}


@router.post("/analytics/event")
async def analytics_event(_: dict = None):
    return {"ok": True}


@router.post("/consent")
async def consent(body: dict, request: Request):
    await db.log_consent(
        (body or {}).get("consent_type") or "",
        bool((body or {}).get("accepted")),
        (body or {}).get("categories") or [],
        _client_ip(request),
        (body or {}).get("session_id") or request.headers.get("x-session-id", ""),
    )
    return {"ok": True}
