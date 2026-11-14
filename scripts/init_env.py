"""Create or update local .env and .env.ai from the example files.

- Missing files are created from the examples.
- Existing files keep every value they have; keys added to the examples
  later are appended, so pulling new config never wipes your secrets.
- Empty secret fields get random values. DB_PASSWORD is yours to set.
Nothing is printed except file names and which keys were added.
"""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED = {"SESSION_SECRET", "BAIT_SECRET", "ADMIN_TOKEN"}


def parse(lines: list[str]) -> dict[str, str]:
    pairs = {}
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            pairs[key.strip()] = value.strip()
    return pairs


def fill(key: str, value: str) -> str:
    return secrets.token_urlsafe(32) if key in GENERATED and not value else value


def sync(example: str, target: str) -> None:
    src, dst = ROOT / example, ROOT / target
    template = src.read_text(encoding="utf-8").splitlines()
    if not dst.exists():
        out = []
        for line in template:
            key, sep, value = line.partition("=")
            out.append(f"{key}={fill(key.strip(), value.strip())}" if sep and not line.startswith("#") else line)
        dst.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"wrote {target}")
        return
    current = dst.read_text(encoding="utf-8").splitlines()
    have = parse(current)
    missing = [(k, v) for k, v in parse(template).items() if k not in have]
    if missing:
        current += [f"{k}={fill(k, v)}" for k, v in missing]
        dst.write_text("\n".join(current) + "\n", encoding="utf-8")
    print(f"{target}: kept existing values" + (f", added {', '.join(k for k, _ in missing)}" if missing else ""))


if __name__ == "__main__":
    sync(".env.example", ".env")
    sync(".env.ai.example", ".env.ai")
