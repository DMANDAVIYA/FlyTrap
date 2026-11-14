"""Controller settings from the environment (.env shared values plus .env.ai keys). Model names: models.py."""

import os
from dataclasses import dataclass, field


def _csv(name: str, default: str) -> list[str]:
    return [p.strip() for p in os.getenv(name, default).split(",") if p.strip()]


@dataclass(frozen=True)
class Settings:
    events_db_url: str = os.getenv("EVENTS_DB_URL", "")
    admin_token: str = os.getenv("ADMIN_TOKEN", "")
    bait_secret: str = os.getenv("BAIT_SECRET", "dev-bait-secret")
    gateway_admin_url: str = os.getenv("GATEWAY_ADMIN_URL", "http://gateway-admin:8081")
    rebuilder_url: str = os.getenv("REBUILDER_URL", "http://rebuilder:8050")
    crowd_url: str = os.getenv("CROWD_URL", "http://crowd:8040")
    raider_slots: list[str] = field(default_factory=lambda: _csv("RAIDERS", "raider-1,raider-2,raider-3,raider-4,raider-5"))
    raider_copies: int = int(os.getenv("RAIDER_COPIES", "3"))  # copies of each raider per release
    raider_max_steps: int = int(os.getenv("RAIDER_MAX_STEPS", "40"))
    raider_max_minutes: float = float(os.getenv("RAIDER_MAX_MINUTES", "10"))
    blue_interval_s: float = float(os.getenv("BLUE_INTERVAL_S", "3"))


settings = Settings()
