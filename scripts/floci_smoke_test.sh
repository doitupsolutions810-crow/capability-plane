#!/usr/bin/env bash
set -euo pipefail
export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://127.0.0.1:4566}"
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
aws --endpoint-url="$AWS_ENDPOINT_URL" s3 ls s3://capability-evidence || true
aws --endpoint-url="$AWS_ENDPOINT_URL" sqs get-queue-url --queue-name capability-audit || true
echo "[+] floci smoke ok"
