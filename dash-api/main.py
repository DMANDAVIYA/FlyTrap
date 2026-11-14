"""dash-api, live mode: tails events-db, serves the dashboard (port 8090).

Env: EVENTS_DB_URL, CONTROLLER_URL, RUNS_DIR (default ./runs), RECORD_RUNS (default 1).
Run: uvicorn main:app --host 0.0.0.0 --port 8090
No database? Use `python mock_feed.py` instead: same API, scripted storyline.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import uvicorn

from api import create_app
from live import LiveBackend

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

HERE = Path(__file__).resolve().parent
DSN = os.environ.get("EVENTS_DB_URL", "postgresql://flytrap:flytrap@localhost:5432/flytrap")
CONTROLLER_URL = os.environ.get("CONTROLLER_URL", "http://localhost:8070")
RUNS_DIR = Path(os.environ.get("RUNS_DIR", HERE / "runs"))
RECORD = os.environ.get("RECORD_RUNS", "1") != "0"

app = create_app(LiveBackend(DSN, CONTROLLER_URL), RUNS_DIR, record=RECORD)

if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8090")))
