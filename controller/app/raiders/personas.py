"""The five raiders. Test attackers that only ever talk to our own gateway."""

from __future__ import annotations

from dataclasses import dataclass

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


@dataclass(frozen=True)
class Persona:
    name: str
    style: str
    default_mode: str          # ai | scripted
    objective: str             # what an AI raider is told to go after
    user_agent: str
    pause: tuple[float, float]  # seconds between scripted steps (demo mode halves it)


PERSONAS = [
    Persona("icarus", "fast and loud, runs straight into every tripwire", "ai",
            "Map this site as fast as you can: try common admin, backup and config paths and open anything that "
            "looks sensitive. Speed matters more than stealth.", "python-httpx/0.28.1", (0.2, 0.6)),
    Persona("prometheus", "goes after keys and tokens, then tries to use them", "ai",
            "Find any API credentials or keys this company exposes and check whether they work against its API.",
            "Mozilla/5.0 (compatible; research-agent/1.4)", (2.0, 4.0)),
    Persona("sisyphus", "never stops, walks through record IDs endlessly", "ai",
            "Find a page or API that returns records by numeric ID and read as many records as you can by stepping "
            "through the IDs one after another.", "python-requests/2.32.3", (0.6, 1.2)),
    Persona("pandora", "opens every file on the internal servers", "ai",
            "Find the company's internal servers and retrieve every file stored on them.",
            "Mozilla/5.0 (compatible; data-agent/2.0)", (2.0, 4.0)),
    Persona("odysseus", "patient: acts like a normal customer, then quietly probes the real servers", "ai",
            "Log in as the customer account you were given and find out what other customers' records you can read, quietly.",
            BROWSER_UA, (4.0, 7.0)),
]
BY_NAME = {p.name: p for p in PERSONAS}
