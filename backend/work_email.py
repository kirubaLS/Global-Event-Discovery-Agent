"""
backend/work_email.py - server-side corporate-email check.

Mirrors frontend/src/lib/workEmail.js (keep the two lists in sync).
The frontend already blocks free providers in the UI; this is the
backstop for anyone hitting the API directly.
"""

FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.co.uk", "yahoo.co.in", "ymail.com", "rocketmail.com",
    "hotmail.com", "outlook.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com",
    "protonmail.com", "proton.me", "pm.me",
    "zoho.com",
    "gmx.com", "gmx.net",
    "mail.com", "inbox.com",
    "rediffmail.com",
    "yandex.com", "yandex.ru",
}

WORK_EMAIL_ERROR = ("Please use your company work email, "
                    "not a personal address (e.g. Gmail, Yahoo).")


def email_domain(email: str) -> str:
    at = (email or "").rfind("@")
    return "" if at == -1 else email[at + 1:].strip().lower()


def is_valid_work_email(email: str) -> bool:
    """True only for a plausible corporate address."""
    e = (email or "").strip()
    domain = email_domain(e)
    if "@" not in e or not domain or "." not in domain:
        return False
    return domain not in FREE_EMAIL_DOMAINS


# ── Deep verification: is this a REAL company mailbox domain? ────────
# Free-domain blocklist alone lets invented domains through
# ("ceo@totallyrealcompany123.com"). An MX lookup proves the domain
# actually exists and receives mail. Disposable providers are rejected
# outright. Results are cached per-domain in Redis for 24h.

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com",
    "tempmail.com", "temp-mail.org", "throwawaymail.com", "yopmail.com",
    "sharklasers.com", "getnada.com", "dispostable.com", "maildrop.cc",
    "trashmail.com", "fakeinbox.com", "mintemail.com", "mytemp.email",
    "tempinbox.com", "emailondeck.com", "mohmal.com", "burnermail.io",
    "spamgourmet.com", "mailnesia.com", "tempr.email", "discard.email",
    "33mail.com", "anonaddy.com", "simplelogin.io", "duckduckgo.com",
}

DISPOSABLE_EMAIL_ERROR = ("Disposable email addresses are not accepted - "
                          "please use your company work email.")
NO_MX_ERROR = ("This email domain doesn't appear to receive mail - "
               "please check the address or use your company work email.")


async def verify_work_email(email: str) -> tuple:
    """Full server-side check: (ok, reason).
    Layers: syntax → free provider → disposable provider → live DNS MX
    lookup (cached 24h). DNS infrastructure failures fail OPEN (a
    resolver outage must never block real signups) - only a definitive
    "domain does not exist / has no mail server" fails the email."""
    e = (email or "").strip()
    domain = email_domain(e)
    if "@" not in e or not domain or "." not in domain:
        return False, WORK_EMAIL_ERROR
    if domain in FREE_EMAIL_DOMAINS:
        return False, WORK_EMAIL_ERROR
    if domain in DISPOSABLE_DOMAINS:
        return False, DISPOSABLE_EMAIL_ERROR

    import cache
    cache_key = f"mx:{domain}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return (True, "") if cached.get("ok") else (False, NO_MX_ERROR)

    ok = True
    definitive = False
    try:
        import dns.asyncresolver
        import dns.resolver
        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = 3.0
        try:
            answers = await resolver.resolve(domain, "MX")
            ok = len(list(answers)) > 0
            definitive = True
        except dns.resolver.NXDOMAIN:
            ok = False           # domain does not exist at all
            definitive = True
        except dns.resolver.NoAnswer:
            # No MX record - some real companies receive mail via an
            # A-record fallback; check the domain resolves at all.
            try:
                await resolver.resolve(domain, "A")
                ok = True
                definitive = True
            except Exception:
                ok = False
                definitive = True
        except Exception:
            ok = True            # timeout / resolver trouble → fail open
    except ImportError:
        ok = True                # dnspython missing → fail open

    if definitive:
        await cache.set_json(cache_key, {"ok": ok}, ttl_seconds=86400)
    return (True, "") if ok else (False, NO_MX_ERROR)
