# AVRONE ↔ Capability Plane: leased transactional outbox

**Review state:** isolated SQLite outbox proposal. Not a live dispatcher, not a JetStream client, not proof of exactly-once execution.

## Why this change exists

At source revision \`102554b1adb416a552fdf9f9792ce7578ca941c4\`, \`admin/durable_outbox.py\` imported \`.outbox.OutboxEvent\`, but \`admin/outbox.py\` does not exist in this repository. Its \`claim_batch()\` selected without reserving rows, its duplicate-key handler returned an existing event even for a conflicting payload, and its \`jetstream_publish_fn()\` printed a message without checking any broker acknowledgment. These flaws violate the separation between queue intent and actual delivery.

This branch makes the SQLite outbox self-contained, adds an in-place additive migration for legacy tables, and keeps old rows. It does **not** repair the repository's other missing admin or AttestPipe modules or deploy a producer.

## Durable operation invariant

The logical event key is \`(event_type, aggregate_id)\`. The first valid payload fixes that key. A replay with byte-equivalent canonical JSON returns its persisted event ID; a replay with different canonical JSON raises \`OutboxConflict\`. The payload is bounded (64 KiB) and must be strict finite JSON.

Workers acquire a unique \`claim_token\` with \`BEGIN IMMEDIATE\` and a finite \`lease_until\`. Only the holder of a currently unexpired token may mark that event published or failed. An expired worker cannot finalize after lease loss. \`claim_batch\` is safe against simultaneous independent SQLite connections. Recovery after a worker crash is by lease expiry.

A real publisher must **explicitly return True** only after its destination acknowledges this exact event. Errors, False and missing acknowledgments keep the event pending for retry. The \`jetstream_publish_fn()\` helper raises unless an authenticated transport callback is configured; it is not a real JetStream implementation.

### Cross-repository status semantics

| Producer/consumer | Required evidence |
|---|---|
| AVRONE Trinity / PR #19 | Durable operation ID, request digest and idempotent retry; a dispatch receipt means **queued**, not complete |
| Capability Authority / PR #17 | Signed, audience-scoped capability; issuance replay conflict and method-scoped rights |
| Swarm VM Runner / PR #3 | Signed enqueue acknowledgment and separate specialist completion evidence |
| Capability Plane (this module) | Persisted outbox event; leased delivery attempt; explicit broker acknowledgment |
| Attested History / PR #2 | Separately validated ledger integrity and trusted signature/provenance before promotion |
| Great Scale | Signed orientation and quantitative residuals are scientific evidence, not authorization |

Every stage must preserve \`operation_id\`, \`source_revision\`, \`event_id\`, \`request_digest\`, \`status\`, and evidence pointers in an independently verifiable envelope. This module only handles the outbox \`event_id\` and transport acknowledgment; it must not fabricate the rest.

## Run local tests

\`\`\`bash
python3 -m unittest discover -s tests -v
\`\`\`

Focused validation (Python 3.13.5): 12 tests passed, including 8 competing independent database connections over 80 events, 10 simultaneous duplicate enqueues, lease expiry/fencing, bad payloads, no-ack failure, and legacy schema migration. Both committed file Git blob hashes match the locally tested bytes. The full repository suite, deployment, real broker, process-kill fault injection and signed downstream receipt verification remain untested.

## Activation and compatibility gate

1. Take a backup of the SQLite DB and deploy the compatible two-column schema migration.
2. Update all publisher callers to provide a real transport callback which returns True only on broker acknowledgment.
3. Review caller compatibility: \`mark_published\` and \`mark_failed\` now require the claimed token. That is deliberate fail-closed behavior.
4. Require downstream idempotency keyed by immutable event ID, because lost acknowledgments may cause duplicate publish attempts.
5. Run concurrent *process-level* and crash/restart tests on a real storage volume, then require exact-head CI and security review before merging.
6. The missing upstream \`admin/admin_action.py\`, \`admin/reconcile.py\`, \`admin/suspend_tenant.py\` and associated provider modules are **separate unresolved integration gaps**; this outbox does not claim a runnable full stack.

No automatic merge, live operator action, secret material, side-effect invocation, or production permission change occurs in this branch.
