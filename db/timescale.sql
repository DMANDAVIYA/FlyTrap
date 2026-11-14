-- Optional upgrade, applied by db/setup.sh only when TimescaleDB is installed.
-- events becomes a hypertable; stats_1m becomes a real-time continuous aggregate.

CREATE EXTENSION IF NOT EXISTS timescaledb;

SELECT create_hypertable('events', 'ts', if_not_exists => TRUE, migrate_data => TRUE);

DROP VIEW IF EXISTS stats_1m;

CREATE MATERIALIZED VIEW IF NOT EXISTS stats_1m
  WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
  SELECT time_bucket('1 minute', ts) AS bucket, side, kind, count(*) AS n
  FROM events
  GROUP BY bucket, side, kind
  WITH NO DATA;

SELECT add_continuous_aggregate_policy('stats_1m',
  start_offset => INTERVAL '2 hours',
  end_offset => INTERVAL '1 minute',
  schedule_interval => INTERVAL '1 minute',
  if_not_exists => TRUE);
