#!/bin/sh
# Starts the container. On the first start of the API (SEED_DEMO=1) it fills the database with the Day 1-4 demo journey,
# so the console and Phoenix have something to show. Later starts keep the data in the /data volume.
set -e
if [ "$SEED_DEMO" = "1" ] && [ ! -f /data/.seeded ] && [ "$1" = "uvicorn" ]; then
  # wait for Phoenix to accept traces before running the journey, so every agent step is exported
  if [ -n "$PHOENIX_ENDPOINT" ]; then
    base=$(echo "$PHOENIX_ENDPOINT" | sed 's#/v1/traces##')
    echo "Waiting for Phoenix at $base ..."
    i=0
    until curl -fsS "$base" >/dev/null 2>&1 || [ $i -ge 60 ]; do i=$((i+1)); sleep 2; done
  fi
  echo "Seeding the demo journey (fictional data, fake models) ..."
  python -m scripts.run_journey --reset --quiet || echo "Seeding failed: the app will start empty."
  touch /data/.seeded
fi
exec "$@"
