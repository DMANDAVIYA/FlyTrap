"""Contents of the stray files under the site root (/.env, /.git/config, /backup.zip).

Every secret in them is this visitor's own derived value (see ledger.show),
plus anything planted for the visitor at that place.
"""

import io
import zipfile

from app import ledger
from app.models import Planted

ENV_NAMES = {
    "api_token": "HL_API_TOKEN",
    "cloud_key_id": "HL_OBJECT_STORE_KEY_ID",
    "cloud_secret": "HL_OBJECT_STORE_SECRET",
    "migration_pw": "HL_MIGRATION_PASSWORD",
}
ZIP_DATE = (2026, 11, 12, 3, 14, 0)


def env_text(place: str, extra: list[Planted]) -> str:
    lines = [
        "# hlabs-web production settings",
        "APP_ENV=production",
        "APP_DEBUG=false",
        "APP_URL=https://hackumass-labs.example",
        "DATABASE_URL=postgresql://hlabs_app:Wq7v2mLr9xTb@db-primary.internal:5432/hlabs",
        "REDIS_URL=redis://cache-01.internal:6379/0",
        "",
        "# platform API key used by the deploy job",
        f"HL_API_TOKEN={ledger.show('api_token', place)}",
        "",
        "# object storage for model artifacts",
        f"HL_OBJECT_STORE_KEY_ID={ledger.show('cloud_key_id', place)}",
        f"HL_OBJECT_STORE_SECRET={ledger.show('cloud_secret', place)}",
        "HL_OBJECT_STORE_BUCKET=hlabs-model-artifacts",
        "HL_OBJECT_STORE_REGION=us-east-2",
        "",
        "BACKUP_HOST=backup-01",
        "REGISTRY_HOST=model-vault",
        "SESSION_COOKIE=hl_auth",
    ]
    for index, row in enumerate(extra, start=2):
        lines.append(f"{ENV_NAMES.get(row.kind, 'HL_' + row.kind.upper())}_{index}={row.value}")
    return "\n".join(lines) + "\n"


def git_config() -> str:
    token = ledger.show("api_token", "git")
    return (
        "[core]\n"
        "\trepositoryformatversion = 0\n"
        "\tfilemode = true\n"
        "\tbare = false\n"
        "\tlogallrefupdates = true\n"
        '[remote "origin"]\n'
        f"\turl = https://deploy-bot:{token}@git.hackumass-labs.example/platform/hlabs-web.git\n"
        "\tfetch = +refs/heads/*:refs/remotes/origin/*\n"
        '[branch "main"]\n'
        "\tremote = origin\n"
        "\tmerge = refs/heads/main\n"
    )


def backup_zip() -> bytes:
    files = {
        "hlabs-web/README.txt": "Config snapshot taken before the Postgres 16 migration (ops ticket OPS-2291).\n"
                                "Restore with: unzip backup.zip -d /srv && systemctl restart hlabs-web\n",
        "hlabs-web/.env": env_text("zip", []),
        "hlabs-web/deploy/hosts.txt": "web      hl-web-03 hl-web-04 hl-web-05\n"
                                      "db       db-primary.internal\n"
                                      "backups  backup-01\n"
                                      "models   model-vault\n",
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in files.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=ZIP_DATE), content)
    return buffer.getvalue()
