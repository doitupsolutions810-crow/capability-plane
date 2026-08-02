"""Minimal policy gate — same authorize() shape as capability-policy."""
from __future__ import annotations

from typing import Any


class PolicyError(Exception):
    pass


class PolicyEngine:
    def __init__(self, max_ttl: int = 300, allowed_prefixes: list[str] | None = None):
        self.max_ttl = max_ttl
        self.allowed_prefixes = allowed_prefixes or [
            "spiffe://prod/agent/",
            "spiffe://prod/broker/",
        ]

    def authorize(
        self,
        caller: str,
        rights: list[dict[str, Any]],
        constraints: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        if not any(caller.startswith(p) for p in self.allowed_prefixes):
            raise PolicyError("caller not allowed by trust domain prefixes")
        if ttl_seconds > self.max_ttl:
            raise PolicyError("TTL exceeds maximum")
        for r in rights:
            res = r.get("resource") or ""
            if r.get("type") == "Execute" and not res.startswith("tool."):
                raise PolicyError(f"Execute resource not allowed: {res}")
        if any(r.get("type") == "Execute" for r in rights):
            if "rate_limit" not in constraints:
                constraints["rate_limit"] = {"count": 5, "window_seconds": 60}
