#!/bin/sh
# Create the two databases on your PostgreSQL and apply the event-log schema.
# Run with:  docker compose run --rm db-setup
# Idempotent: safe to run again. The site (hlabs) creates its own tables.
set -eu

export PGPASSWORD="$DB_PASSWORD"
export PGOPTIONS="-c client_min_messages=warning"
conn() { psql -v ON_ERROR_STOP=1 -q -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$@"; }

for db in "$EVENTS_DB_NAME" "$REAL_DB_NAME"; do
  if [ "$(conn -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'")" = "1" ]; then
    echo "database $db exists"
  else
    conn -d postgres -c "CREATE DATABASE \"$db\""
    echo "created database $db"
  fi
done

conn -d "$EVENTS_DB_NAME" -f /db/init.sql
echo "event-log schema applied to $EVENTS_DB_NAME"

if [ "$(conn -d "$EVENTS_DB_NAME" -tAc "SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")" = "1" ]; then
  conn -d "$EVENTS_DB_NAME" -f /db/timescale.sql
  echo "TimescaleDB found: events is a hypertable, stats_1m a continuous aggregate"
else
  echo "TimescaleDB not installed: using plain tables and a plain stats_1m view"
fi
