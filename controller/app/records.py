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


def by_type(records: Iterable[str]) -> Counter:
    """Total records per type, e.g. Counter({'user': 500, 'api_token': 12})."""
    totals: Counter = Counter()
    for rec in records:
        totals[rec.split(":")[0]] += count(rec)
    return totals
