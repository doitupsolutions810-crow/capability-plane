"""Mesh bounds: trust_domain, policy_version, delegation_depth."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


def load_acceptance(path: str = "config/acceptance_policy.yaml") -> dict[str, Any]:
    p = Path(path)
    if not p.exists() or yaml is None:
        return {
            "expected_trust_domain": "prod",
            "allowed_policy_versions": [1, 2, 3, 4, 5],
            "max_delegation_depth": 3,
        }
    return yaml.safe_load(p.read_text()) or {}


def check_bounds(cap: dict[str, Any], acceptance: dict[str, Any]) -> str | None:
    td = acceptance.get("expected_trust_domain", "prod")
    if cap.get("trust_domain") != td:
        return "trust domain mismatch"
    allowed = acceptance.get("allowed_policy_versions") or []
    if allowed and int(cap.get("policy_version") or -1) not in allowed:
        return "policy_version not allowed"
    max_d = int(acceptance.get("max_delegation_depth") or 3)
    if int(cap.get("delegation_depth") or 0) > max_d:
        return "delegation_depth exceeded"
    return None
