"""Parse the record ledger the site reports in X-Edge-Records ("user:41", "invoice:9001-9020")."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable


def count(record: str) -> int:
    """'user:41' -> 1, 'invoice:9001-9020' -> 20."""
    _, _, ident = record.partition(":")
    first, sep, last = ident.partition("-")
    if sep and first.isdigit() and last.isdigit():
        return max(0, int(last) - int(first) + 1)
    return 1


def ids(records: Iterable[str], kind: str, limit: int = 1000) -> list[int]:
    """Distinct ids of one record type with ranges expanded: ['user:3-5', 'user:9'] -> [3, 4, 5, 9]."""
    found: set[int] = set()
    for rec in records:
        rtype, _, ident = rec.partition(":")
        first, sep, last = ident.partition("-")
        if rtype != kind or not first.isdigit() or (sep and not last.isdigit()):
            continue
        low = int(first)
        high = min(int(last) if sep else low, low + limit)
        found.update(range(low, high + 1))
        if len(found) >= limit:
            break
    return sorted(found)[:limit]


def exposure(real_pages: Iterable[tuple[str, list[str]]]) -> tuple[int | None, list[int]]:
    """(the visitor's own customer id, other customers' ids) from the real site's (path, records) pairs.
    Own = the customer its /account page showed, else the customer it was served most often."""
    pages = list(real_pages)
    seen: Counter = Counter(i for _, recs in pages for i in ids(recs, "user"))
    account = next((ids(recs, "user") for path, recs in pages if path == "/account" and ids(recs, "user")), [])
    own = account[0] if account else (seen.most_common(1)[0][0] if seen else None)
    return own, sorted(i for i in seen if i != own)


def by_type(records: Iterable[str]) -> Counter:
    """Total records per type, e.g. Counter({'user': 500, 'api_token': 12})."""
    totals: Counter = Counter()
    for rec in records:
        totals[rec.split(":")[0]] += count(rec)
    return totals
