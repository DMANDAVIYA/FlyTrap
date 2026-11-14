"""Gateway settings, read once from the environment."""

import os
from dataclasses import dataclass, field
from ipaddress import IPv4Network, ip_network


def _csv(name: str, default: str) -> list[str]:
    return [p.strip() for p in os.getenv(name, default).split(",") if p.strip()]


@dataclass(frozen=True)
class Settings:
    events_db_url: str = os.getenv("EVENTS_DB_URL", "")
    session_secret: str = os.getenv("SESSION_SECRET", "dev-session-secret")
    admin_token: str = os.getenv("ADMIN_TOKEN", "")
    admin_bind: str = os.getenv("ADMIN_BIND", "127.0.0.1")
    edge_subnet: IPv4Network = field(default_factory=lambda: ip_network(os.getenv("EDGE_SUBNET", "172.31.0.0/24")))
    risk_flip: int = int(os.getenv("RISK_FLIP", "60"))
    risk_review: int = int(os.getenv("RISK_REVIEW", "30"))
    pod_idle_reset_min: float = float(os.getenv("POD_IDLE_RESET_MIN", "10"))
    pods: list[str] = field(default_factory=lambda: _csv("PODS", "pod-1,pod-2,pod-3,pod-4,pod-5"))
    real_upstreams: list[str] = field(default_factory=lambda: _csv("REAL_UPSTREAMS", "web-1,web-2"))
    upstream_port: int = 8000
    public_port: int = 8080
    admin_port: int = 8081
    max_body_scan: int = 64 * 1024


settings = Settings()
