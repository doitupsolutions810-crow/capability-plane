#!/usr/bin/env bash
set -euo pipefail
ENDPOINT="${AWS_ENDPOINT_URL:-http://127.0.0.1:4566}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_EC2_METADATA_DISABLED=true
echo "[*] Floci bootstrap at $ENDPOINT"
aws --endpoint-url="$ENDPOINT" sts get-caller-identity >/dev/null
aws --endpoint-url="$ENDPOINT" s3 mb "s3://capability-evidence" 2>/dev/null || true
aws --endpoint-url="$ENDPOINT" sqs create-queue --queue-name capability-audit >/dev/null || true
echo "[+] done"
