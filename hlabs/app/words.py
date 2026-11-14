"""Words that must never appear in anything the site serves (spec 2.10)."""

FORBIDDEN = ("pod", "trap", "honeypot", "fake", "flytrap", "edge", "canary")


def is_clean(text: str) -> bool:
    lowered = text.lower()
    return not any(word in lowered for word in FORBIDDEN)
