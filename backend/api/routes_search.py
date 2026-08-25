"""
backend/api/routes_search.py - /api/search via ChatGPT web search,
plus tiny stubs for the endpoints the (unchanged) frontend still calls.

The old pipeline (DB, scrapers, embeddings, queue, analytics, consent)
is gone. Every stub returns the safe "empty" shape its caller already
handles gracefully - see frontend/src/api/client.js.
"""
import asyncio
import uuid

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
    # Render sits behind a proxy - real client IP is the first entry
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
    # Corporate email only - free/disposable providers and domains that
    # don't actually receive mail (no MX record) are all rejected.
    email = (req.profile.get("email") or "").strip()
    if email:
        ok, reason = await verify_work_email(email)
        if not ok:
            raise HTTPException(status_code=422, detail=reason)
        # Proof-of-mailbox: the email must have completed OTP verification
        # (valid 30 days). Only enforced when an OTP sender (SMTP or
        # Resend) and the DB are configured - without them there is no
        # code to have entered.
        if otp_sender_configured():
            verified = await db.is_email_verified(email)
            if verified is False:
                raise HTTPException(status_code=403, detail="email_not_verified")

    ip         = _client_ip(request)
    device_id  = request.headers.get("x-device-id", "")
    session_id = request.headers.get("x-session-id", "")

    # Daily cap: IP and device are limited independently - exceeding
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

    # Cache hit → return inline immediately (no waiting, no job).
    cached = await cache.get_cached_search(req.profile)
    if cached is not None:
        sub_id = await db.log_submission(req.profile, ip, device_id, session_id, True)
        await db.log_search_result(sub_id, cached)
        return {"status": "done", "job_id": None, "result": cached}

    # Cache miss → run the slow GPT search in the BACKGROUND and return a
    # job id the frontend polls (api.pollSearchStatus). A synchronous
    # 2-3 min gpt-5 request is fragile on Render (a redeploy or proxy
    # timeout strands it mid-flight and the page hangs forever); the
    # queued pattern survives that — the browser polls a fast status
    # endpoint instead of holding one long connection open.
    job_id = str(uuid.uuid4())
    await _set_job(job_id, {"status": "processing"})
    asyncio.create_task(
        _run_search_job(job_id, dict(req.profile), ip, device_id, session_id)
    )
    return {"status": "queued", "job_id": job_id}


# In-memory job store (single Render instance — fine for this scale).
_JOBS: dict = {}


async def _set_job(job_id: str, value: dict) -> None:
    _JOBS[job_id] = value
    # Mirror to Redis (10 min TTL) so a finished result survives an
    # in-memory wipe / brief instance change and any poll can fetch it.
    await cache.set_json(f"job:{job_id}", value, ttl_seconds=600)


async def _run_search_job(job_id: str, profile: dict, ip: str,
                          device_id: str, session_id: str) -> None:
    try:
        result = await run_gpt_event_search(profile)
        if result.get("events"):
            await cache.set_cached_search(profile, result)
        sub_id = await db.log_submission(profile, ip, device_id, session_id, False)
        await db.log_search_result(sub_id, result)
        await _set_job(job_id, {"status": "done", "result": result})
    except RuntimeError as e:               # missing API key
        await _set_job(job_id, {"status": "error", "error": str(e)})
    except Exception as e:
        logger.error(f"GPT event search failed: {e}")
        await _set_job(job_id, {"status": "error", "error": "Search failed - please try again."})


@router.get("/search/status/{job_id}")
async def search_status(job_id: str):
    job = _JOBS.get(job_id) or await cache.get_json(f"job:{job_id}")
    if not job:
        # Unknown id: the job never existed, or the instance restarted
        # mid-search and lost the running task. Retryable, not a hang.
        return {"status": "error", "error": "Search expired - please try again."}
    return job


# ── Maintenance + stats ─────────────────────────────────────────────

@router.get("/maintenance-status")
async def maintenance_status():
    return {"maintenance": settings.maintenance_mode,
            "message": settings.maintenance_message}


@router.get("/stats")
async def stats():
    # Static marketing-level numbers; the event DB no longer exists.
    return {
        "total_events_in_db": 17000,
        "countries_covered": 129,
        "live_sources": 1,
        "top_event_names": [],
        "resend_enabled": bool(settings.resend_api_key),
    }


# ── Form-helper stubs (frontend falls back to its local logic) ──────

class ParseIcpRequest(BaseModel):
    text: str = ""


class ValidateEmailRequest(BaseModel):
    email: str = ""


class VerifyCodeRequest(BaseModel):
    email: str = ""
    code: str = ""


def _code_hash(email: str, code: str) -> str:
    import hashlib
    return hashlib.sha256(f"{email.lower()}:{code.strip()}".encode()).hexdigest()


def _otp_email_html(code: str) -> str:
    return f"""
        <div style="font-family:Helvetica,Arial,sans-serif;max-width:420px;margin:0 auto;padding:24px;">
          <h2 style="color:#1E2B33;margin:0 0 6px;">Verify your work email</h2>
          <p style="color:#4B5A63;font-size:14px;line-height:1.6;">
            Enter this code on ExpoToFunnel to see your event ranking:</p>
          <div style="background:#F4F1EA;border-radius:10px;padding:18px;text-align:center;
                      font-size:32px;font-weight:800;letter-spacing:8px;color:#0E7C6B;">{code}</div>
          <p style="color:#8A959C;font-size:12px;margin-top:14px;">
            The code expires in 10 minutes. If you didn't request it, ignore this email.</p>
        </div>"""


def otp_sender_configured() -> bool:
    """OTP delivery order: Brevo HTTP API → SMTP → Resend.

    OTP_ENABLED is the master pause switch (config.py): while it is
    off this returns False, so /search skips the verified-email check
    and /send-verification tells the form to skip the code step. The
    sending code below stays wired up and works the moment it's on."""
    if not settings.otp_enabled:
        return False
    return bool(settings.brevo_api_key or settings.smtp_host or settings.resend_api_key)


async def _send_otp_brevo(to: str, code: str) -> None:
    """Brevo transactional-email HTTP API - port 443, so it works on
    Render's free tier where outbound SMTP ports are blocked."""
    import httpx
    sender = settings.brevo_from_email or settings.smtp_from or settings.resend_from_email
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": settings.brevo_api_key,
                     "content-type": "application/json"},
            json={
                "sender": {"name": "ExpoToFunnel", "email": sender},
                "to": [{"email": to}],
                "subject": f"{code} is your ExpoToFunnel verification code",
                "htmlContent": _otp_email_html(code),
            },
        )
        r.raise_for_status()


def _send_otp_smtp(to: str, code: str) -> None:
    """Send the OTP over plain SMTP (Google Workspace app password,
    Brevo SMTP key, or any other provider). Blocking - call via
    asyncio.to_thread."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    sender = settings.smtp_from or settings.smtp_user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{code} is your ExpoToFunnel verification code"
    msg["From"] = f"ExpoToFunnel <{sender}>"
    msg["To"] = to
    msg.attach(MIMEText(f"Your ExpoToFunnel verification code is {code}. "
                        "It expires in 10 minutes.", "plain"))
    msg.attach(MIMEText(_otp_email_html(code), "html"))

    if int(settings.smtp_port) == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.login(settings.smtp_user, settings.smtp_pass)
            s.sendmail(sender, [to], msg.as_string())
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.starttls()
            s.login(settings.smtp_user, settings.smtp_pass)
            s.sendmail(sender, [to], msg.as_string())


def _send_otp_resend(to: str, code: str) -> None:
    import resend
    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": f"ExpoToFunnel <{settings.resend_from_email}>",
        "to": [to],
        "subject": f"{code} is your ExpoToFunnel verification code",
        "html": _otp_email_html(code),
    })


async def _send_otp_email(to: str, code: str) -> None:
    """Delivery chain: Brevo HTTP API → SMTP → Resend. The first
    configured sender that succeeds wins; each failure logs and falls
    through, keeping Resend's quota for PDF reports whenever possible."""
    import asyncio
    if settings.brevo_api_key:
        try:
            await _send_otp_brevo(to, code)
            return
        except Exception as e:
            logger.error(f"Brevo OTP send failed: {e}")
            if not (settings.smtp_host or settings.resend_api_key):
                raise
            logger.info("Falling back past Brevo for this OTP")
    if settings.smtp_host:
        try:
            await asyncio.to_thread(_send_otp_smtp, to, code)
            return
        except Exception as e:
            logger.error(f"SMTP OTP send failed ({settings.smtp_host}): {e}")
            if not settings.resend_api_key:
                raise
            logger.info("Falling back to Resend for this OTP")
    await asyncio.to_thread(_send_otp_resend, to, code)


@router.post("/send-verification")
async def send_verification(req: ValidateEmailRequest, request: Request):
    """Email a 6-digit OTP. This is the proof-of-mailbox step: a fake
    address at a real company never receives the code, so it can never
    pass. 3 sends/hour per email or IP."""
    email = (req.email or "").strip().lower()
    ok, reason = await verify_work_email(email)
    if not ok:
        raise HTTPException(status_code=422, detail=reason)
    if not otp_sender_configured():
        return {"sent": False, "skip": True}   # email infra off → frontend skips OTP
    ip = _client_ip(request)
    if await db.sends_in_last_hour(email, ip) >= 3:
        raise HTTPException(status_code=429,
                            detail="Too many codes requested - try again in an hour.")
    import secrets
    code = f"{secrets.randbelow(1_000_000):06d}"
    stored = await db.create_verification(email, _code_hash(email, code), ip)
    if not stored:
        return {"sent": False, "skip": True}   # no DB → cannot enforce, skip
    try:
        await _send_otp_email(email, code)
    except Exception as e:
        logger.error(f"OTP send failed: {e}")
        raise HTTPException(status_code=502,
                            detail="Couldn't send the code - please try again.")
    return {"sent": True, "skip": False}


@router.post("/verify-email-code")
async def verify_email_code(req: VerifyCodeRequest):
    email = (req.email or "").strip().lower()
    code = (req.code or "").strip()
    if not email or not code:
        raise HTTPException(status_code=422, detail="Enter the 6-digit code from your email.")
    status = await db.check_verification_code(email, _code_hash(email, code))
    if status == "ok":
        return {"verified": True}
    if status == "wrong":
        raise HTTPException(status_code=422, detail="That code isn't right - check the email and try again.")
    if status == "expired":
        raise HTTPException(status_code=422, detail="This code has expired - request a new one.")
    return {"verified": True}   # storage unavailable → fail open


@router.post("/validate-email")
async def validate_email(req: ValidateEmailRequest):
    """Live corporate-email check for the forms (ICP + contact): free
    providers, disposable providers, and domains with no mail server
    (MX lookup, Redis-cached 24h) are rejected. The search and
    email-report endpoints re-verify server-side regardless - this
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
    """LLM parse of the raw buyer text - powers the live role+industry
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
            # Chips are a few short arrays - cap hard so a runaway reply
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
