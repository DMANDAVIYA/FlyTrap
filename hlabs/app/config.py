"""Settings from the environment. APP_ROLE never changes normal page output."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    role: str = os.getenv("APP_ROLE", "real")              # real | pod
    database_url: str = os.getenv("DATABASE_URL", "sqlite:////data/pod.db")
    session_secret: str = os.getenv("SESSION_SECRET", "dev-session-secret")
    bait_secret: str = os.getenv("BAIT_SECRET", "dev-bait-secret")
    node_name: str = os.getenv("NODE_NAME", "web-1")
    template_db: str = os.getenv("TEMPLATE_DB", "/templates/pod.db")
    backup_host: str = os.getenv("BACKUP_HOST", "http://backup-01:8000")
    vault_host: str = os.getenv("VAULT_HOST", "http://model-vault:8000")

    @property
    def is_pod(self) -> bool:
        return self.role == "pod"


settings = Settings()
