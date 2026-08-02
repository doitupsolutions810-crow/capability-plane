#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export ATTESTPIPE_MIRROR_SQS="${ATTESTPIPE_MIRROR_SQS:-0}"
export PLANE_BASE_URL="${PLANE_BASE_URL:-http://127.0.0.1:8088}"
if ! curl -sf -o /dev/null -X POST "$PLANE_BASE_URL/v1/capabilities/issue" -H 'Content-Type: application/json' -d '{"rights":[]}' 2>/dev/null; then
  echo "[*] Starting plane"
  python3 plane_service/server.py > /tmp/dev_plane.log 2>&1 &
  sleep 1
fi
echo "[*] Running pipeline"
python3 runtime/execute_pipeline.py
echo "[+] E2E complete"
