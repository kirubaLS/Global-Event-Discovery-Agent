"""
backend/api/routes_search.py — /api/search via ChatGPT web search,
plus tiny stubs for the endpoints the (unchanged) frontend still calls.

The old pipeline (DB, scrapers, embeddings, queue, analytics, consent)
is gone. Every stub returns the safe "empty" shape its caller already
handles gracefully — see frontend/src/api/client.js.
"""
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from config import get_settings
from gpt_search import run_gpt_event_search

router = APIRouter()
settings = get_settings()


class SearchRequest(BaseModel):
    profile: dict
    captcha_token: str = ""
    honeypot: str = ""
    consent: bool = False


@router.post("/search")
async def search(req: SearchRequest):
    if req.honeypot:                       # bots fill the hidden field
        raise HTTPException(status_code=400, detail="Invalid submission.")
    if not (req.profile.get("buyer_description") or req.profile.get("target_industries")):
        raise HTTPException(status_code=422, detail="Describe your buyer first.")
    try:
        result = await run_gpt_event_search(req.profile)
    except RuntimeError as e:              # missing API key → clear 503
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"GPT event search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed - please try again.")
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
async def consent(_: dict = None):
    return {"ok": True}
