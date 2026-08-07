"""
backend/work_email.py — server-side corporate-email check.

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
