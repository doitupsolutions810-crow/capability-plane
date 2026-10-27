# Capability Rights Contract v1

A capability authorizes a request only when audience, expiry, type, resource, and method match exactly. Missing requested methods, missing granted methods, malformed expiry, and implicit method wildcards fail closed. Expiry is exclusive: now_ts >= expires_at is expired.

Attenuation must preserve or reduce exact (type, resource, method) tuples. The checked-in dashboard caller accepts either a one-element `rights` array or flat `resource`/`method` fields, but requires exactly one complete right per intent and rejects missing methods before issuing a capability. The full-stack adapter/runtime sources are not present in this repository snapshot; those callers remain blocked pending the release archive and their concrete method semantics.

The conformance test reads its vectors directly from contracts/capability-rights-v1.json, so test expectations cannot drift from the frozen contract.

Verification status: local core and dashboard caller regressions pass. Exact-head hosted CI and compatibility review of omitted runtime callers are still required before merge. This change is not deployed.
