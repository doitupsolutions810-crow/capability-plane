"""Executor — sole side-effect path + rate limit + bounds + receipt."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict

from .bounds import check_bounds, load_acceptance
from .core import verify
from .crypto_sign import sign, verify_sig


class RateLimiter:
    def __init__(self) -> None:
        self.windows: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, max_count: int, window_seconds: int) -> bool:
        now = time.time()
        q = self.windows[key]
        cutoff = now - window_seconds
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= max_count:
            return False
        q.append(now)
        return True


class Executor:
    def __init__(self) -> None:
        self.rate_limiter = RateLimiter()
        self.crl: set[str] = set()
        self.acceptance = load_acceptance()

    def execute(
        self,
        cap: dict[str, Any],
        signature: str,
        required: dict[str, Any],
        caller: str,
    ) -> dict[str, Any]:
        if cap.get("id") in self.crl:
            return {"status": "error", "error": "revoked"}
        if not verify_sig(cap, signature):
            return {"status": "error", "error": "invalid signature"}
        err = check_bounds(cap, self.acceptance)
        if err:
            return {"status": "error", "error": err}
        if not verify(cap, required, caller):
            return {"status": "error", "error": "verify failed"}
        rl = (cap.get("constraints") or {}).get("rate_limit") or {}
        count = int(rl.get("count") or 5)
        window = int(rl.get("window_seconds") or 60)
        key = f"{cap.get('id')}:{required.get('type')}:{required.get('resource')}"
        if not self.rate_limiter.allow(key, count, window):
            return {"status": "error", "error": "rate limited"}

        action = f"{required.get('type')}:{required.get('resource')}"
        receipt = {
            "capability_id": cap["id"],
            "executor_id": "plane-executor-1",
            "action": action,
            "outcome": "ok",
            "timestamp": time.time(),
        }
        receipt["signature"] = sign(receipt)
        return {"status": "ok", "result": "executed", "receipt": receipt}
