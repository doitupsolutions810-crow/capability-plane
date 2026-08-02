#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bash scripts/start_stack.sh
export PYTHONPATH="$ROOT"
export PLANE_BASE_URL="${PLANE_BASE_URL:-http://127.0.0.1:8443}"
export ATTESTPIPE_MIRROR_SQS="${ATTESTPIPE_MIRROR_SQS:-1}"
export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://127.0.0.1:4566}"
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
export AWS_EC2_METADATA_DISABLED=true
echo "[*] E2E via front door ($PLANE_BASE_URL)"
python3 runtime/execute_pipeline.py
echo "[+] done"
