# Evolution horizons — Unified Capability System Plane

## Present (built)

- Broker + Executor separation, frozen OpenAPI
- Ed25519 capability + receipt signatures
- Policy gate + acceptance bounds
- Front door path allowlist
- AttestPipe events (client pipeline + server-side)
- Control12 Intent adapter, watsonx skill OpenAPI
- Floci evidence/audit backends (dev)
- Mesh/profile configs, measurement policy placeholders
- Sovereign OS operator view contracts

## Horizon A — Production control plane

Rust broker-server API-compatible swap, SPIFFE, signed policy bundles, real cloud evidence/audit, TLS front door, watsonx prod import.

## Horizon B — Confidential multi-cloud mesh

Nitro / SEV-SNP / TDX adapters, measurement pinning, continuous re-attest, report_data binding.

## Horizon C — Evidence & compliance platform

Evidence index, receipt verification, durable AttestPipe bus, Sovereign audit timeline.

## Horizon D — Policy-as-code governance

Cedar/Rego → plane rules, offline governance roots, Intent rejection with policy reasons.

## Horizon E — Sovereign agentic OS

Control12 planners only emit Intent; all tools behind Executor; AttestPipe + Sovereign UI as control tower.

## Non-goals

Ambient shell/C2, long-lived god tokens, UI or bus minting capabilities.
