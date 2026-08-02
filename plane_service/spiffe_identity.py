"""SPIFFE identity for Horizon A.

Production: fetch from Workload API Unix socket.
Dev: fall back to PLANE_SPIFFE_ID / synthetic agent id.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkloadIdentity:
    spiffe_id: str
    trust_domain: str
    source: str  # workload-api | env | fallback


def _parse_trust_domain(spiffe_id: str) -> str:
    if not spiffe_id.startswith("spiffe://"):
        return os.environ.get("PLANE_TRUST_DOMAIN", "prod")
    rest = spiffe_id[len("spiffe://") :]
    return rest.split("/", 1)[0] or "prod"


def fetch_workload_identity(
    socket_path: Optional[str] = None,
    trust_domain_cfg: Optional[str] = None,
) -> WorkloadIdentity:
    env_id = os.environ.get("PLANE_SPIFFE_ID") or os.environ.get("SPIFFE_ID")
    socket = socket_path or os.environ.get("SPIFFE_ENDPOINT_SOCKET")

    if socket and os.path.exists(socket.replace("unix://", "")):
        # Real SPIRE Workload API client goes here
        pass

    if env_id:
        td = trust_domain_cfg or _parse_trust_domain(env_id)
        return WorkloadIdentity(env_id, td, "env")

    td = trust_domain_cfg or os.environ.get("PLANE_TRUST_DOMAIN", "prod")
    return WorkloadIdentity(
        f"spiffe://{td}/agent/dev",
        td,
        "fallback",
    )
