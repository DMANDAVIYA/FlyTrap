"""Settings, read once from the environment (spec 10.1)."""

import os
import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    role: str  # "real" or "pod"
    database_url: str
    session_secret: str
    bait_secret: str
    pod_name: str = ""
    node_name: str = "web"
    template_db: str = "/templates/pod.db"

    @property
    def is_pod(self) -> bool:
        return self.role == "pod"


def load_settings() -> Settings:
    role = os.environ.get("APP_ROLE", "real")
    if role not in ("real", "pod"):
        raise ValueError(f"APP_ROLE must be real or pod, got {role!r}")
    return Settings(
        role=role,
        database_url=os.environ["DATABASE_URL"],
        session_secret=os.environ["SESSION_SECRET"],
        bait_secret=os.environ["BAIT_SECRET"],
        pod_name=os.environ.get("POD_NAME", ""),
        node_name=os.environ.get("NODE_NAME", socket.gethostname()),
        template_db=os.environ.get("POD_TEMPLATE_DB", "/templates/pod.db"),
    )
