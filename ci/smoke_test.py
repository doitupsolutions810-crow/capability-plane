#!/usr/bin/env python3
"""CI smoke test for capability-plane: the crypto core must round-trip and
must reject tampering. Run from the repo root:  python ci/smoke_test.py
Exits non-zero on any failure."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    from plane_service.core import issue, verify
    from plane_service.crypto_sign import sign, verify_sig
    from plane_service.executor import Executor
    from plane_service.policy import PolicyEngine

    caller = "spiffe://prod/agent/dev"
    rights = [{"type": "read", "resource": "demo"}]
    PolicyEngine().authorize(caller, rights, {}, 60)
    cap = issue(caller, "spiffe://prod/broker", rights, {}, 60, "prod", "dev:unattested", 1)
    sig = sign(cap)

    if not verify_sig(cap, sig):
        print("FAIL: signature does not verify on an untampered capability")
        return 1
    if not verify(cap, rights[0], caller):
        print("FAIL: verify() rejected a freshly issued capability")
        return 1
    out = Executor().execute(cap, sig, rights[0], caller)
    if out.get("status") != "ok":
        print(f"FAIL: executor refused a valid capability: {out}")
        return 1

    tampered = dict(cap)
    tampered["rights"] = [{"type": "admin", "resource": "*"}]
    if verify_sig(tampered, sig):
        print("FAIL: tampered capability still verifies — signature is not binding")
        return 1

    print("PASS: issue -> sign -> verify -> execute round-trip; tamper rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
