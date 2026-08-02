#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/config/tls}"
mkdir -p "$OUT"
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$OUT/front_door.key" \
  -out "$OUT/front_door.crt" \
  -days 365 \
  -subj "/CN=capability-plane.local" \
  -addext "subjectAltName=DNS:localhost,DNS:capability-plane.local,IP:127.0.0.1"
echo "Wrote $OUT/front_door.crt and $OUT/front_door.key"
