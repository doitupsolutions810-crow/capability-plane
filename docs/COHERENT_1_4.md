# Coherent Tracks 1–4

Integrated evolution of the Capability Plane + Admin Control Plane.

| Track | Deliverable | Env / entry |
|-------|-------------|-------------|
| **1 Durability** | `admin/durable_outbox.py` SQLite outbox + JetStream-shaped publisher; Postgres SQL in `admin/schema/outbox_events.sql` | `OUTBOX_DB_PATH`, `NATS_URL` |
| **2 Identity** | `plane_service/spiffe_identity.py` Workload API → env → fallback; trust-domain allowlist | `SPIFFE_ENDPOINT_SOCKET`, `PLANE_SPIFFE_ID` |
| **3 Providers** | `admin/providers/factory.py` generic \| kubernetes \| cloud into SuspendTenantService | `PROVIDER_ADAPTER` |
| **4 Ship / Horizon A** | `scripts/run_coherent_1_4.sh` broker + front door (+TLS) + admin API | `FRONT_DOOR_TLS=1` |

```bash
cd artifacts/capability-authority
export PYTHONPATH=$PWD ALLOW_ADMIN_DESTRUCTIVE_ACTIONS=true
bash scripts/run_coherent_1_4.sh
```
