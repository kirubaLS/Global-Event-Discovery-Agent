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
from work_email import is_valid_work_email, verify_work_email, WORK_EMAIL_ERROR

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
    # Corporate email only — free/disposable providers and domains that
    # don't actually receive mail (no MX record) are all rejected.
    email = (req.profile.get("email") or "").strip()
    if email:
        ok, reason = await verify_work_email(email)
        if not ok:
            raise HTTPException(status_code=422, detail=reason)

    ip         = _client_ip(request)
    device_id  = request.headers.get("x-device-id", "")
    session_id = request.headers.get("x-session-id", "")

    # Daily cap: IP and device are limited independently — exceeding
    # either blocks. Redis is the primary counter; if it's unreachable
    # the submissions table is the fallback so the limit survives a
    # Redis outage (only both layers down fails open).
    limit_msg = await cache.check_rate_limit(device_id, ip)
    if limit_msg == "redis_down":
        if await db.count_searches_today(ip, device_id) >= settings.search_daily_limit > 0:
            limit_msg = (f"Daily search limit reached ({settings.search_daily_limit}/day). "
                         "Try again tomorrow, or contact us for more.")
        else:
            limit_msg = None
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


class ValidateEmailRequest(BaseModel):
    email: str = ""


@router.post("/validate-email")
async def validate_email(req: ValidateEmailRequest):
    """Live corporate-email check for the forms (ICP + contact): free
    providers, disposable providers, and domains with no mail server
    (MX lookup, Redis-cached 24h) are rejected. The search and
    email-report endpoints re-verify server-side regardless — this
    endpoint just gives the user instant feedback."""
    ok, reason = await verify_work_email(req.email)
    return {"valid": ok, "reason": reason}


_PARSE_PROMPT = """Extract the buyer targeting from this B2B ICP text. Reply with ONE JSON object only:
{
  "personas": ["<role titles, e.g. CIO, Head of Procurement>"],
  "industries": ["<industries/verticals, e.g. NBFC / Non-Bank Lending, Manufacturing>"],
  "segments": [{"personas": ["<role>"], "industries": ["<industry>"]}],
  "extra_keywords": ["<other targeting words worth keeping, e.g. mid-market, APAC>"]
}
Rules: use the user's own vocabulary (expand well-known abbreviations, e.g. NBFC → "NBFC / Non-Bank Lending"); `segments` pairs each role with the industry it was stated with ("CEOs at BFSI, CIOs at Medtech" → 2 segments); if the text is industry-agnostic ("CIOs across all industries") leave industries empty; never invent targeting that is not in the text; empty arrays are fine."""


@router.post("/parse-icp")
async def parse_icp(req: ParseIcpRequest):
    """LLM parse of the raw buyer text — powers the live role+industry
    chips in the ICP form. No keyword tables: the model reads the exact
    wording. Falls back to {"source":"rules"} on any failure so the form
    never breaks. Results cached in Redis for 7 days (debounced typing
    and repeat visitors hit the same strings constantly)."""
    text = (req.text or "").strip()
    if len(text) < 4:
        return {"source": "rules"}
    if not settings.openai_api_key:
        return {"source": "rules"}

    import hashlib
    key = f"parse:{hashlib.sha256(text.lower().encode()).hexdigest()}"
    cached = await cache.get_json(key)
    if cached:
        return cached

    try:
        import json as _json
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=8)
        kwargs = dict(
            model=settings.openai_parse_model,
            input=[{"role": "system", "content": _PARSE_PROMPT},
                   {"role": "user", "content": text}],
            # Chips are a few short arrays — cap hard so a runaway reply
            # can never make the form feel slow or cost real money.
            max_output_tokens=300,
        )
        if settings.openai_parse_model.lower().startswith(("gpt-5", "o1", "o3", "o4")):
            kwargs["reasoning"] = {"effort": "minimal"}
        resp = await client.responses.create(**kwargs)
        raw = resp.output_text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`\n")
            raw = raw[raw.find("{"):]
        data = _json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        result = {
            "source": "llm",
            "personas": [str(p) for p in (data.get("personas") or [])][:6],
            "industries": [str(i) for i in (data.get("industries") or [])][:6],
            "segments": [
                {"personas": [str(p) for p in (s.get("personas") or [])],
                 "industries": [str(i) for i in (s.get("industries") or [])]}
                for s in (data.get("segments") or []) if isinstance(s, dict)
            ][:4],
            "extra_keywords": [str(k) for k in (data.get("extra_keywords") or [])][:8],
        }
        await cache.set_json(key, result)
        return result
    except Exception as e:
        logger.warning(f"parse-icp LLM failed: {e}")
        return {"source": "rules"}


@router.get("/geo-list")
async def geo_list():
    return {"countries": []}               # ICPForm falls back to GEO_OPTIONS


@router.get("/geo-hint")
async def geo_hint():
    return {}


@router.get("/city-hint")
async def city_hint():
    return {"exact_match": True, "suggestions": []}


# ── Analytics: stored in Postgres (fire-and-forget on the client) ───

@router.post("/analytics/session/start")
async def analytics_session_start(body: dict, request: Request):
    await db.upsert_session(
        (body or {}).get("session_id") or request.headers.get("x-session-id", ""),
        (body or {}).get("referrer") or "",
        (body or {}).get("landing_page") or "",
        _client_ip(request),
        request.headers.get("user-agent", ""),
    )
    return {"ok": True}


@router.post("/analytics/session/heartbeat")
async def analytics_heartbeat(body: dict, request: Request):
    await db.session_heartbeat(
        (body or {}).get("session_id") or request.headers.get("x-session-id", ""),
        (body or {}).get("delta_seconds") or 0,
    )
    return {"ok": True}


@router.post("/analytics/event")
async def analytics_event(body: dict, request: Request):
    await db.log_activity(
        (body or {}).get("session_id") or request.headers.get("x-session-id", ""),
        (body or {}).get("event_type") or "",
        (body or {}).get("submission_id") or "",
        (body or {}).get("event_id") or "",
        (body or {}).get("metadata") or {},
        _client_ip(request),
    )
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
