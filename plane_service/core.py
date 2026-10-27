"""Pure capability core — mirrors capability-core contracts (frozen)."""
from __future__ import annotations

import math
import time
import uuid
from typing import Any, Optional


def now() -> float:
    return time.time()


def issue(caller: str, issuer: str, rights: list[dict[str, Any]], constraints: dict[str, Any], ttl_seconds: int, trust_domain: str, broker_measurement: Optional[str], policy_version: int) -> dict[str, Any]:
    issued_at = now()
    return {"id": str(uuid.uuid4()), "issuer": issuer, "audience": caller, "rights": rights, "constraints": constraints, "issued_at": issued_at, "expires_at": issued_at + ttl_seconds, "parent_id": None, "nonce": str(uuid.uuid4()), "trust_domain": trust_domain, "broker_measurement": broker_measurement, "policy_version": policy_version, "delegation_depth": 0}


def attenuate(cap: dict[str, Any], new_rights: list[dict[str, Any]]) -> dict[str, Any]:
    old = {(r.get("type"), r.get("resource"), r.get("method")) for r in cap.get("rights") or []}
    for r in new_rights:
        if (r.get("type"), r.get("resource"), r.get("method")) not in old:
            raise ValueError("amplification forbidden")
    out = dict(cap)
    out["id"] = str(uuid.uuid4())
    out["rights"] = new_rights
    out["issued_at"] = now()
    out["parent_id"] = cap["id"]
    out["nonce"] = str(uuid.uuid4())
    out["delegation_depth"] = int(cap.get("delegation_depth") or 0) + 1
    return out


def verify(cap: dict[str, Any], required: dict[str, Any], caller: str, now_ts: Optional[float] = None) -> bool:
    """Fail closed unless audience, expiry, type, resource, and method match."""
    ts = now_ts if now_ts is not None else now()
    try:
        expires_at = float(cap.get("expires_at") or 0)
    except (TypeError, ValueError, OverflowError):
        return False
    if not math.isfinite(expires_at) or ts >= expires_at:
        return False
    if cap.get("audience") not in (caller, "*"):
        return False
    required_type = required.get("type")
    required_resource = required.get("resource")
    required_method = required.get("method")
    if not all(isinstance(value, str) and value for value in (required_type, required_resource, required_method)):
        return False
    for right in cap.get("rights") or []:
        if not isinstance(right, dict):
            continue
        if right.get("type") == required_type and right.get("resource") == required_resource and right.get("method") == required_method:
            return True
    return False
