"""Create or update local .env and .env.ai from the example files.

- Missing files are created from the examples.
- Existing files keep every value they have; keys added to the examples later
  are appended, so pulling new config never wipes your secrets.
- A key that is empty in your file gets the example's default when the example
  has one (e.g. model chains). Keys and passwords have empty defaults in the
  examples, so they are never filled in.
- Empty secret fields (SESSION_SECRET, BAIT_SECRET, ADMIN_TOKEN) get random values.
  DB_PASSWORD and API keys are yours to set.
Nothing is printed except file names and which keys changed.
"""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED = {"SESSION_SECRET", "BAIT_SECRET", "ADMIN_TOKEN"}


def is_setting(line: str) -> bool:
    return "=" in line and not line.lstrip().startswith("#")


def parse(lines: list[str]) -> dict[str, str]:
    return {k.strip(): v.strip() for k, _, v in (l.partition("=") for l in lines if is_setting(l))}


def initial(key: str, default: str) -> str:
    return secrets.token_urlsafe(32) if key in GENERATED and not default else default


def sync(example: str, target: str) -> None:
    src, dst = ROOT / example, ROOT / target
    template = src.read_text(encoding="utf-8").splitlines()
    defaults = parse(template)

    if not dst.exists():
        lines = [f"{k.strip()}={initial(k.strip(), v.strip())}" if is_setting(l) else l
                 for l, (k, _, v) in ((l, l.partition("=")) for l in template)]
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {target}")
        return

    lines = dst.read_text(encoding="utf-8").splitlines()
    filled = []
    for i, line in enumerate(lines):
        if not is_setting(line):
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not value.strip() and defaults.get(key):
            lines[i] = f"{key}={defaults[key]}"
            filled.append(key)
    have = parse(lines)
    added = [k for k in defaults if k not in have]
    lines += [f"{k}={initial(k, defaults[k])}" for k in added]
    if filled or added:
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    changes = [f"added {', '.join(added)}" if added else "", f"filled defaults for {', '.join(filled)}" if filled else ""]
    print(f"{target}: kept existing values" + "".join(f"; {c}" for c in changes if c))


if __name__ == "__main__":
    sync(".env.example", ".env")
    sync(".env.ai.example", ".env.ai")
