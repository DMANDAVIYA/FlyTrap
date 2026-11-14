#!/bin/sh
# Real instances seed Postgres once (locked, idempotent); every other instance starts from the template copy.
set -e
if [ "$APP_ROLE" = "pod" ]; then
  mkdir -p /data
  cp /templates/pod.db /data/pod.db
else
  until python -m app.seed --role real; do echo "database not ready, retrying"; sleep 2; done
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-server-header --no-access-log --proxy-headers
