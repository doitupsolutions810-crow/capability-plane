# Sovereign Agentic OS Dashboard

Unifies Horizons 1–5 as read/act surfaces over the Capability Plane.

```bash
export PLANE_BASE_URL=http://127.0.0.1:8090
export PLANE_SPIFFE_ID=spiffe://prod/agent/dashboard
python3 sovereign/dashboard/app.py
# open http://127.0.0.1:8501
```

| Horizon | Card |
|---------|------|
| 1 Production plane | health, SPIFFE, TLS |
| 2 Mesh | broker directory, measurement policy |
| 3 Evidence | recent evidence files |
| 4 Policy | acceptance policy, version |
| 5 OS console | Intent → Issue → Verify → Execute |

TLS production: `config/caddy.front_door.Caddyfile` or `config/nginx.front_door.conf`
SPIRE: set `SPIFFE_ENDPOINT_SOCKET` and `pip install spiffe`
