-- Dolos events database. Plain PostgreSQL; idempotent, safe to re-run.
-- The events table is the append-only source of truth; everything else
-- (sessions, stats, reports) is state or a view derived from it.
-- If TimescaleDB is installed, db/timescale.sql upgrades events to a
-- hypertable and stats_1m to a continuous aggregate.

CREATE TABLE IF NOT EXISTS events (
  id          BIGSERIAL,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
  session_id  TEXT NOT NULL,
  kind        TEXT NOT NULL,   -- request | tripwire | flip | canary | beacon | action | thought | note | alert | lockdown | report | pod_reset | pod_shared
  side        TEXT,            -- real | trap | blocked
  pod         TEXT,
  src_ip      INET,
  method      TEXT,
  path        TEXT,
  query       TEXT,
  status      INT,
  req_bytes   INT,
  resp_bytes  INT,
  latency_ms  REAL,
  gw_ms       REAL,
  user_agent  TEXT,
  tripwire    TEXT,
  records     TEXT[],
  payload     JSONB,
  PRIMARY KEY (id, ts)
);
CREATE INDEX IF NOT EXISTS events_session_ts ON events (session_id, ts DESC);
CREATE INDEX IF NOT EXISTS events_kind_ts ON events (kind, ts DESC);
CREATE INDEX IF NOT EXISTS events_id ON events (id);

CREATE TABLE IF NOT EXISTS sessions (
  session_id  TEXT PRIMARY KEY,
  first_seen  TIMESTAMPTZ NOT NULL,
  last_seen   TIMESTAMPTZ NOT NULL,
  fingerprint TEXT,
  src_ip      INET,
  user_agent  TEXT,
  side        TEXT NOT NULL DEFAULT 'real',
  pod         TEXT,
  flipped_by  TEXT,
  flip_kind   TEXT,
  risk        INT  NOT NULL DEFAULT 0,
  pace        TEXT NOT NULL DEFAULT 'normal',
  label       TEXT NOT NULL DEFAULT 'unknown',
  confidence  REAL,
  reasons     JSONB,
  stage       TEXT NOT NULL DEFAULT 'recon',
  ladder      TEXT NOT NULL DEFAULT 'watch',
  raider      TEXT,
  ended       BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS canaries (
  value       TEXT PRIMARY KEY,
  kind        TEXT NOT NULL,
  session_id  TEXT NOT NULL,
  location    TEXT,
  planted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  fired_at    TIMESTAMPTZ,
  fired_by    TEXT,
  fired_event BIGINT
);

CREATE TABLE IF NOT EXISTS actions (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor       TEXT NOT NULL,   -- athena | argus | hephaestus | cerberus | mnemosyne | clio | hermes | zeus | charon
  tool        TEXT NOT NULL,
  session_id  TEXT,
  args        JSONB,
  reason      TEXT NOT NULL,
  evidence    BIGINT[],
  status      TEXT NOT NULL    -- done | rejected | pending_approval | approved | cancelled
);

CREATE TABLE IF NOT EXISTS approvals (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
  kind        TEXT NOT NULL,   -- release | new_rule | virtual_patch | lockdown | rebuild
  action_id   BIGINT REFERENCES actions(id),
  summary     TEXT NOT NULL,
  payload     JSONB,
  status      TEXT NOT NULL DEFAULT 'pending',
  decided_by  TEXT,
  decided_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS agent_notes (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
  agent       TEXT NOT NULL,
  session_id  TEXT,
  note        TEXT NOT NULL,
  evidence    BIGINT[]
);
CREATE INDEX IF NOT EXISTS agent_notes_ts ON agent_notes (ts DESC);

CREATE TABLE IF NOT EXISTS campaigns (
  id          BIGSERIAL PRIMARY KEY,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  name        TEXT NOT NULL,
  session_ids TEXT[] NOT NULL,
  reason      TEXT NOT NULL,
  evidence    BIGINT[]
);

CREATE TABLE IF NOT EXISTS fingerprints (
  id             BIGSERIAL PRIMARY KEY,
  session_id     TEXT,
  user_agent     TEXT,
  src_ip         INET,
  path_signature TEXT,
  timing         JSONB,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reports (
  session_id  TEXT PRIMARY KEY,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  report      JSONB NOT NULL,
  markdown    TEXT NOT NULL
);

-- Per-minute counts behind the dashboard counters. A plain view here;
-- db/timescale.sql replaces it with a continuous aggregate.
CREATE OR REPLACE VIEW stats_1m AS
  SELECT date_trunc('minute', ts) AS bucket, side, kind, count(*) AS n
  FROM events
  GROUP BY 1, 2, 3;
