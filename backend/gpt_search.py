"""
backend/gpt_search.py — ICP → top-6 events via ChatGPT real web search.

This replaces the entire old pipeline (DB, scrapers, ingestion APIs,
embeddings, scorers). One call: the raw ICP form payload goes into a
strict prompt, ChatGPT's web_search tool finds real upcoming events,
and the reply comes back as JSON already shaped for the frontend
(ShowRankingPage / ShowDeepDivePage / EmailReportModal all read these
exact field names — do not rename them).

Verification policy baked into the prompt:
  • events must exist on the live web (organiser page found via search)
  • geography is HARD: "CEO at healthcare in India" → India events only
  • persona must plausibly attend (CEO-level content, not a nurses' CME)
  • dates must fall inside the requested window and be in the future
  • source_url must be the official event/registration page
  • unknown numbers → 0 / "" — never invented
"""
import json
import re
import uuid
from datetime import date

from loguru import logger

from config import get_settings

settings = get_settings()

# ═══════════════════════════════════════════════════════════════════
# GPT TEMPLATE — system prompt
# (Kept in sync with GPT_EVENT_SEARCH_TEMPLATE.md at the repo root,
#  which is the copy-paste version for manual ChatGPT use.)
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a B2B event-intelligence researcher for LeadStrategus. Your ONLY job: given an Ideal Customer Profile (ICP), use REAL web search to find the top 6 upcoming, VERIFIED, in-person B2B events (conferences, trade shows, summits, expos) where that ICP's target buyers will actually attend.

NON-NEGOTIABLE RULES
1. VERIFIED EVENTS ONLY. Every event must have a live official website or registration page that you actually found via web search. Never invent an event, an edition, a date, a venue, or a URL. If you cannot verify it, it does not go in the list.
2. GEOGRAPHY IS A HARD FILTER. If the ICP says India, return ONLY events physically held in India. Never substitute Dubai/Singapore/US events "because they are bigger". If fewer than 6 verified events exist in the geography + date window, return fewer than 6 and explain in `search_notes` — a short honest list beats a padded one.
3. PERSONA ATTENDANCE IS A HARD FILTER. Ask for each candidate: "would the stated persona (e.g. a CEO of a healthcare company in India) genuinely attend this?" A CEO attends leadership summits, industry flagship expos, investor/innovation conferences — not an academic paper workshop or a technicians' training day. Drop events the persona would not attend.
4. DATE WINDOW IS A HARD FILTER. Only events whose start date is in the future AND inside the requested date window (date_from → date_to). Confirm the date is for the UPCOMING edition, not last year's page.
5. NO FABRICATED NUMBERS. est_attendees must come from the organiser's site or credible coverage of the latest edition. If unknown, use 0 — never guess. Same for pricing and sponsors: unknown → empty string.
6. URLS: `event_link` and `source_url` must be the official event website (deep link to the specific upcoming edition, e.g. a page containing the year). `registration_url` is the ticket/registration page if it exists, else "". Never use Google search links, LinkedIn, Facebook, Wikipedia, meetup.com, or venue-only websites (hotel/expo-centre homepages).
7. RANKING. Rank 1 → 6 by: (a) density of the exact target persona+industry, (b) event size/seniority of audience, (c) date proximity inside the window, (d) city relevance if cities were given. relevance_score is 0–100 and must be consistent with the rank order.
8. BE EXHAUSTIVE BEFORE YOU ANSWER. Search multiple ways (e.g. "<industry> conference <country> 2026", "<industry> expo <city>", "<persona> summit <country>", plus 10times/industry association listings) so no major qualifying event is missed. Missing an obvious flagship event is a failure.

OUTPUT FORMAT
Reply with ONE JSON object and NOTHING else — no prose, no markdown fences.
{
  "search_notes": "<1-3 sentences: how many verified events found, any gaps/caveats>",
  "events": [
    {
      "rank": 1,
      "event_name": "",
      "date": "YYYY-MM-DD",            // start date of the upcoming edition
      "end_date": "YYYY-MM-DD",        // same as date if one-day
      "place": "City, Country",
      "venue": "",                      // exact venue/hall if published, else ""
      "event_link": "https://…",        // official event site (edition-specific)
      "registration_url": "https://…",  // ticket/registration page, "" if none
      "source_url": "https://…",        // page where you verified date+venue
      "what_its_about": "",             // 2-3 sentences, factual
      "key_numbers": "",                // e.g. "15,000+ attendees · 500 exhibitors · 200 speakers" (published figures only)
      "industry": "",                   // comma-separated industries served
      "buyer_persona": "",              // comma-separated attendee roles, most senior first
      "est_attendees": 0,               // integer, 0 if not published
      "sponsors": "",                   // comma-separated known sponsors/exhibitors, "" if unknown
      "pricing": "",                    // ticket price range if published, "" if unknown
      "relevance_score": 0,             // 0-100
      "fit_verdict": "GO",              // "GO" (strong fit) or "CONSIDER"
      "verdict_notes": "",              // 1-2 sentences: WHY this ICP should (not) prioritise it, citing persona + geography + size
      "confidence": "high"              // "high" | "medium" | "low" — how well you verified it
    }
  ]
}"""


def build_user_prompt(profile: dict) -> str:
    """Turn the raw ICP form payload into the search brief."""
    today = date.today().isoformat()
    lines = [
        f"TODAY'S DATE: {today}",
        "",
        "ICP (raw form input — treat `buyer_description` as the source of truth; the parsed lists are hints):",
        f"- Buyer description (raw): {profile.get('buyer_description') or '-'}",
        f"- Company: {profile.get('company_name') or '-'}",
        f"- Target industries: {', '.join(profile.get('target_industries') or []) or 'any (infer from buyer description)'}",
        f"- Target personas: {', '.join(profile.get('target_personas') or []) or 'infer from buyer description'}",
        f"- Target geographies (HARD filter — events must be physically held here): {', '.join(profile.get('target_geographies') or []) or 'Global'}",
        f"- Date window (HARD filter): {profile.get('date_from') or today} to {profile.get('date_to') or 'next 12 months'}",
        f"- Average deal size: {profile.get('avg_deal_size_category') or 'medium'}",
        f"- Preferred event types: {', '.join(profile.get('preferred_event_types') or []) or 'conference, trade show, summit, expo'}",
        f"- Extra keywords: {', '.join(profile.get('extra_keywords') or []) or '-'}",
        f"- Existing client names (similar buyers): {', '.join(profile.get('client_names') or []) or '-'}",
    ]
    segs = profile.get("icp_segments") or []
    if segs:
        lines.append(f"- Role+industry segments: {json.dumps(segs)}")
    lines += [
        "",
        "TASK: Using real web search, find and rank the top 6 upcoming verified events matching ALL hard filters, "
        "following every rule in your instructions, and reply with the single JSON object only.",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# OpenAI call + response validation
# ═══════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> dict:
    """The model is told 'JSON only', but strip fences/prose defensively."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object in model reply")
    return json.loads(t[start:end + 1])


_BAD_URL_HOSTS = (
    "google.com", "facebook.com", "linkedin.com", "twitter.com", "x.com",
    "instagram.com", "youtube.com", "wikipedia.org", "meetup.com",
)


def _clean_url(url) -> str:
    u = (url or "").strip() if isinstance(url, str) else ""
    if not u.startswith(("http://", "https://")):
        return ""
    if any(h in u.lower() for h in _BAD_URL_HOSTS):
        return ""
    return u


def _grade_from_score(score: float) -> tuple:
    if score >= 80: return "A+", "Exceptional fit"
    if score >= 65: return "A",  "Strong fit"
    if score >= 50: return "B+", "Good fit"
    if score >= 35: return "B",  "Reasonable fit"
    return "C", "Marginal fit"


def _geo_ok(place: str, geos: list) -> bool:
    """Hard server-side backstop for rule 2: place must mention one of
    the requested geographies (skip when Global / empty)."""
    real = [g for g in (geos or []) if g and g.lower() != "global"]
    if not real:
        return True
    p = (place or "").lower()
    return any(g.lower() in p for g in real)


def _validate_events(raw_events: list, profile: dict) -> list:
    today = date.today().isoformat()
    date_to = profile.get("date_to") or ""
    out = []
    for ev in raw_events or []:
        if not isinstance(ev, dict):
            continue
        name = (ev.get("event_name") or "").strip()
        start = (ev.get("date") or "").strip()
        link = _clean_url(ev.get("event_link")) or _clean_url(ev.get("source_url"))
        if not name or not link:
            continue                      # unverifiable → drop, never show
        if start and start[:10] < today:
            continue                      # past event → drop
        if date_to and start and start[:10] > date_to:
            continue                      # outside requested window → drop
        if not _geo_ok(ev.get("place", ""), profile.get("target_geographies")):
            continue                      # wrong country → drop
        try:
            score = float(ev.get("relevance_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        grade, label = _grade_from_score(score)
        try:
            attendees = int(ev.get("est_attendees") or 0)
        except (TypeError, ValueError):
            attendees = 0
        out.append({
            "event_id":        str(uuid.uuid4()),
            "rank":            len(out) + 1,
            "event_name":      name,
            "date":            start[:10],
            "end_date":        (ev.get("end_date") or start)[:10],
            "place":           ev.get("place") or "",
            "venue":           ev.get("venue") or "",
            "event_link":      link,
            "source_url":      _clean_url(ev.get("source_url")) or link,
            "registration_url": _clean_url(ev.get("registration_url")),
            "website":         link,
            "what_its_about":  ev.get("what_its_about") or "",
            "key_numbers":     ev.get("key_numbers") or "",
            "industry":        ev.get("industry") or "",
            "buyer_persona":   ev.get("buyer_persona") or "",
            "est_attendees":   attendees,
            "sponsors":        ev.get("sponsors") or "",
            "pricing":         ev.get("pricing") or "",
            "relevance_score": max(0.0, min(score, 100.0)),
            "fit_verdict":     "GO" if (ev.get("fit_verdict") == "GO" or score >= 65) else "CONSIDER",
            "fit_grade":       grade,
            "fit_label":       label,
            "verdict_notes":   ev.get("verdict_notes") or "",
            "confidence":      ev.get("confidence") if ev.get("confidence") in ("high", "medium", "low") else "medium",
        })
        if len(out) == 6:
            break
    return out


async def run_gpt_event_search(profile: dict) -> dict:
    """Run the web search and return a SearchResponse-shaped dict
    (the exact shape App.jsx expects from the old backend)."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key,
                         timeout=settings.openai_timeout_seconds)

    resp = await client.responses.create(
        model=settings.openai_search_model,
        tools=[{"type": "web_search"}],
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_user_prompt(profile)},
        ],
    )
    payload = _extract_json(resp.output_text)
    events = _validate_events(payload.get("events"), profile)
    logger.info(f"GPT web search: {len(payload.get('events') or [])} returned, "
                f"{len(events)} survived validation")

    dm_ratio, density = 0.35, lambda e: (e["relevance_score"] or 50) / 100
    total_icps = sum(
        round(e["est_attendees"] * density(e) * dm_ratio / 10) * 10
        for e in events if e["est_attendees"]
    )
    return {
        "profile_id": str(uuid.uuid4()),
        "company_name": profile.get("company_name") or "",
        "events": events,
        "all_relevant_events": [],
        "suggested_geos": [],
        "region_fallback_note": payload.get("search_notes") if len(events) < 3 else None,
        "universe_stats": {
            "total_icps_across_shows": total_icps,
            "shows_worth_considering": len(events),
            "strongly_recommended": sum(1 for e in events if e["fit_grade"] in ("A+", "A")),
            "total_indexed": 0,
        },
        "search_notes": payload.get("search_notes") or "",
    }
