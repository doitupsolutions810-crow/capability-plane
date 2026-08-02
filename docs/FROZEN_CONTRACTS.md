# Frozen contracts (do not break)

## OpenAPI (watsonx / front door)

| Method | Path | Owner |
|--------|------|-------|
| POST | `/v1/capabilities/issue` | Broker |
| POST | `/v1/capabilities/attenuate` | Broker |
| POST | `/v1/capabilities/verify` | Broker |
| POST | `/v1/execute` | **Executor only** |

Source of truth: `watsonx/capability-plane.openapi.yaml`

## AttestPipe message types

- `CapabilityIssued`
- `CapabilityAttenuated`
- `ExecuteReceipt`
- `EvidenceBundleRef`
- `PolicyBundlePublished`
- `CrlBundlePublished`

## Swap map

| Before | After |
|--------|-------|
| `gateway/dev_plane_server.py` | `plane_service/server.py` |
| Front door UPSTREAM_PLANE | broker+executor host |
| Later | Rust broker-server same paths |
