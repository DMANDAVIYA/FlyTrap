"""Create local .env and .env.ai from the example files.

Empty secret fields in .env get random values. Existing files are never
overwritten unless --force is given. Nothing is printed except file names.
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET_KEYS = {"SESSION_SECRET", "BAIT_SECRET", "ADMIN_TOKEN", "REAL_DB_PASSWORD", "EVENTS_DB_PASSWORD"}


def fill(line: str) -> str:
    key, sep, value = line.partition("=")
    if sep and key.strip() in SECRET_KEYS and not value.strip():
        return f"{key}={secrets.token_urlsafe(32)}"
    return line


def write(example: str, target: str, generate: bool, force: bool) -> None:
    src, dst = ROOT / example, ROOT / target
    if dst.exists() and not force:
        print(f"{target} exists, kept (use --force to regenerate)")
        return
    lines = src.read_text(encoding="utf-8").splitlines()
    out = [fill(l) for l in lines] if generate else lines
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    write(".env.example", ".env", generate=True, force=force)
    write(".env.ai.example", ".env.ai", generate=False, force=force)
