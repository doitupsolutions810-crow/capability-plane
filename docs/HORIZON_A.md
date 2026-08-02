# Horizon A — Production-shaped plane

## Goals

1. Real upstream = `plane_service/server.py` (Broker+Executor)
2. Front door as only public entry (TLS optional)
3. SPIFFE identity for Issue audience
4. Frozen OpenAPI + AttestPipe

## Run

```bash
set -a; source config/horizon_a.env; set +a
export PYTHONPATH=$PWD
python3 plane_service/server.py &
# optional TLS:
# bash scripts/gen_front_door_tls.sh
# export FRONT_DOOR_TLS=1 FRONT_DOOR_CERT=config/tls/front_door.crt FRONT_DOOR_KEY=config/tls/front_door.key
python3 gateway/https_front_door.py &
python3 runtime/execute_pipeline.py
```

## SPIFFE

- Dev: `PLANE_SPIFFE_ID=spiffe://prod/agent/dev`
- Prod: set `SPIFFE_ENDPOINT_SOCKET` and implement Workload API client in `spiffe_identity.py`

## TLS

`FRONT_DOOR_TLS=1` + cert/key paths. Prefer Caddy/nginx/envoy in real prod.
