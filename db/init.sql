-- Flytrap events database (TimescaleDB on Postgres 16).
-- The events hypertable is the append-only source of truth; everything else
-- (sessions, stats, reports) is state or a view derived from it.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE events (
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
SELECT create_hypertable('events', 'ts');
CREATE INDEX events_session_ts ON events (session_id, ts DESC);
CREATE INDEX events_kind_ts ON events (kind, ts DESC);
CREATE INDEX events_id ON events (id);

CREATE TABLE sessions (
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

CREATE TABLE canaries (
  value       TEXT PRIMARY KEY,
  kind        TEXT NOT NULL,
  session_id  TEXT NOT NULL,
  location    TEXT,
  planted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  fired_at    TIMESTAMPTZ,
  fired_by    TEXT,
  fired_event BIGINT
);

CREATE TABLE actions (
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

CREATE TABLE approvals (
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

CREATE TABLE agent_notes (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
  agent       TEXT NOT NULL,
  session_id  TEXT,
  note        TEXT NOT NULL,
  evidence    BIGINT[]
);
CREATE INDEX agent_notes_ts ON agent_notes (ts DESC);

CREATE TABLE campaigns (
  id          BIGSERIAL PRIMARY KEY,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  name        TEXT NOT NULL,
  session_ids TEXT[] NOT NULL,
  reason      TEXT NOT NULL,
  evidence    BIGINT[]
);

CREATE TABLE fingerprints (
  id             BIGSERIAL PRIMARY KEY,
  session_id     TEXT,
  user_agent     TEXT,
  src_ip         INET,
  path_signature TEXT,
  timing         JSONB,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reports (
  session_id  TEXT PRIMARY KEY,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  report      JSONB NOT NULL,
  markdown    TEXT NOT NULL
);

-- Continuous aggregate behind the dashboard counters (Tiger Data prize).
CREATE MATERIALIZED VIEW stats_1m
  WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
  SELECT time_bucket('1 minute', ts) AS bucket, side, kind, count(*) AS n
  FROM events
  GROUP BY bucket, side, kind
  WITH NO DATA;

SELECT add_continuous_aggregate_policy('stats_1m',
  start_offset => INTERVAL '2 hours',
  end_offset => INTERVAL '1 minute',
  schedule_interval => INTERVAL '1 minute');
