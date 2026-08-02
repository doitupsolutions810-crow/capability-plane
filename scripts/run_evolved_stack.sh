#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export PLANE_PORT=8090
export FRONT_DOOR_PORT=8443
export UPSTREAM_PLANE=http://127.0.0.1:8090
export PLANE_BASE_URL=http://127.0.0.1:8443
export ATTESTPIPE_MIRROR_SQS="${ATTESTPIPE_MIRROR_SQS:-0}"
mkdir -p /tmp/plane-stack config evidence
python3 plane_service/server.py > /tmp/plane-stack/broker.log 2>&1 &
echo $! > /tmp/plane-stack/broker.pid
sleep 1
UPSTREAM_PLANE=$UPSTREAM_PLANE FRONT_DOOR_PORT=$FRONT_DOOR_PORT \
  python3 gateway/https_front_door.py > /tmp/plane-stack/front.log 2>&1 &
echo $! > /tmp/plane-stack/front.pid
sleep 1
curl -s http://127.0.0.1:8090/health; echo
curl -s http://127.0.0.1:8443/health; echo
python3 runtime/execute_pipeline.py
