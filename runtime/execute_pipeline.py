"""Executor-side pipeline: plane Execute + evidence + AttestPipe publish."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attestpipe.bus import BUS
from attestpipe.messages import CapabilityIssued, EvidenceBundleRef, ExecuteReceiptMsg
from control12.actuation_adapter import Intent, PlaneClient, actuate


def _maybe_store_evidence(capability_id: str, bundle: dict) -> Optional[str]:
    try:
        from floci.evidence_store import put_evidence
        return put_evidence(capability_id, bundle)
    except Exception:
        ev = ROOT / "evidence"
        ev.mkdir(parents=True, exist_ok=True)
        path = ev / f"{capability_id}.json"
        path.write_text(json.dumps(bundle, indent=2))
        return f"file://{path}"


def run_intent(base_url: str, intent: Intent, publish_attestpipe: bool = True) -> dict[str, Any]:
    client = PlaneClient(base_url)
    result = actuate(client, intent)
    out: dict[str, Any] = {
        "status": result.status,
        "error": result.error,
        "verify_valid": result.verify_valid,
        "execute": result.execute,
        "capability_id": (result.capability or {}).get("id"),
    }
    if publish_attestpipe and result.capability:
        BUS.publish(
            CapabilityIssued(
                capability_id=result.capability["id"],
                audience=result.capability.get("audience", ""),
                issuer=result.capability.get("issuer", ""),
                rights=result.capability.get("rights") or [],
                policy_version=int(result.capability.get("policy_version") or 0),
                delegation_depth=int(result.capability.get("delegation_depth") or 0),
                broker_measurement=result.capability.get("broker_measurement"),
                platform="dev",
                expires_at=result.capability.get("expires_at"),
            )
        )
    if result.status == "ok" and result.execute and result.capability:
        receipt = result.execute.get("receipt") or {}
        cap_id = result.capability["id"]
        bundle = {
            "capability": result.capability,
            "signature": result.signature,
            "receipt": receipt,
            "outcome": receipt.get("outcome", result.status),
        }
        uri = _maybe_store_evidence(cap_id, bundle)
        out["evidence_uri"] = uri
        if publish_attestpipe:
            BUS.publish(
                ExecuteReceiptMsg(
                    capability_id=cap_id,
                    executor_id=receipt.get("executor_id", "unknown"),
                    action=receipt.get("action", ""),
                    outcome=receipt.get("outcome", ""),
                    receipt=receipt,
                )
            )
            sha = hashlib.sha256(json.dumps(bundle, sort_keys=True).encode()).hexdigest()
            BUS.publish(
                EvidenceBundleRef(
                    capability_id=cap_id,
                    uri=uri or "",
                    sha256=sha,
                    platform="dev",
                )
            )
    return out


if __name__ == "__main__":
    os.environ.setdefault("ATTESTPIPE_MIRROR_SQS", "0")
    base = os.environ.get("PLANE_BASE_URL", "http://127.0.0.1:8088")
    caller = os.environ.get("PLANE_SPIFFE_ID", "spiffe://prod/agent/dev")
    intent = Intent(
        rights=[{"type": "Execute", "resource": "tool.summarize"}],
        ttl_seconds=60,
        execute_resource="tool.summarize",
        constraints={"rate_limit": {"count": 5, "window_seconds": 60}},
        caller=caller,
    )
    events: list[str] = []
    BUS.subscribe(lambda p: events.append(p.get("message_type", "?")))
    out = run_intent(base, intent)
    print(json.dumps(out, indent=2))
    print("attestpipe_events:", events)
