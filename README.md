# Capability Plane — Full Stack

High-assurance capability control plane for agentic systems.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$PWD
python3 plane_service/server.py &
UPSTREAM_PLANE=http://127.0.0.1:8090 FRONT_DOOR_PORT=8443 \
  python3 gateway/https_front_door.py &
export PLANE_BASE_URL=http://127.0.0.1:8443 ATTESTPIPE_MIRROR_SQS=0
python3 runtime/execute_pipeline.py
```

## Layout

| Path | Role |
|------|------|
| plane_service/ | Broker + Executor (Ed25519, policy, bounds) |
| gateway/ | Front door |
| attestpipe/ | Evidence event bus |
| control12/ | Intent adapter |
| watsonx/ | OpenAPI + agent instructions |
| floci/ | Local AWS emulator |
| config/ | Profiles and policy |
| docs/ | Architecture |
| sovereign/ | Operator views |
| runtime/ | E2E pipeline |
| scripts/ | Bootstrap |

See `docs/FROZEN_CONTRACTS.md`. Never commit private signing keys.
