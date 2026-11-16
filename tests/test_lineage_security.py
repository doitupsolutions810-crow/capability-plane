"""Regression tests for the three executor lineage bypasses.

Each test is named after the attack it closes:
- method confusion (a GET capability executing a DELETE requirement)
- rate-limit reset (attenuating a child to mint a fresh budget)
- revocation bypass (a child of a revoked parent still executing)

Run with pytest, or standalone: python tests/test_lineage_security.py
Requires the `cryptography` package (same as plane_service itself).
Set PLANE_SIGNING_KEY to a scratch path so no real key is touched.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault(
    "PLANE_SIGNING_KEY",
    os.path.join(tempfile.mkdtemp(), "test_broker.pem"))

from plane_service.core import attenuate, issue  # noqa: E402
from plane_service.crypto_sign import sign  # noqa: E402
from plane_service.executor import Executor  # noqa: E402


def mkcap(rights, rate=None):
    constraints = {"rate_limit": rate} if rate else {}
    cap = issue("alice", "broker", rights, constraints, 3600, "prod", None, 1)
    return cap, sign(cap)


def test_method_confusion_refused():
    ex = Executor()
    cap, sig = mkcap([{"type": "data", "resource": "/data/x", "method": "GET"}])
    r = ex.execute(cap, sig, {"type": "data", "resource": "/data/x",
                              "method": "DELETE"}, "alice")
    assert r["status"] == "error", r
    r = ex.execute(cap, sig, {"type": "data", "resource": "/data/x",
                              "method": "GET"}, "alice")
    assert r["status"] == "ok", r


def test_rate_limit_survives_attenuation():
    ex = Executor()
    rights = [{"type": "data", "resource": "/data/y", "method": "GET"}]
    cap, sig = mkcap(rights, rate={"count": 2, "window_seconds": 60})
    req = {"type": "data", "resource": "/data/y", "method": "GET"}
    assert [ex.execute(cap, sig, req, "alice")["status"]
            for _ in range(3)] == ["ok", "ok", "error"]
    child = attenuate(cap, rights)
    assert ex.execute(child, sign(child), req, "alice")["status"] == "error"
    grand = attenuate(child, rights)
    assert ex.execute(grand, sign(grand), req, "alice")["status"] == "error"
    # an unrelated lineage keeps its own budget
    cap2, sig2 = mkcap([{"type": "data", "resource": "/data/o", "method": "GET"}],
                       rate={"count": 2, "window_seconds": 60})
    r = ex.execute(cap2, sig2, {"type": "data", "resource": "/data/o",
                                "method": "GET"}, "alice")
    assert r["status"] == "ok", r


def test_revocation_cascades_to_children():
    ex = Executor()
    rights = [{"type": "data", "resource": "/data/z", "method": "GET"}]
    cap, sig = mkcap(rights)
    child = attenuate(cap, rights)
    grand = attenuate(child, rights)
    req = {"type": "data", "resource": "/data/z", "method": "GET"}
    assert ex.execute(child, sign(child), req, "alice")["status"] == "ok"
    ex.crl.add(cap["id"])
    assert ex.execute(cap, sig, req, "alice")["status"] == "error"
    assert ex.execute(child, sign(child), req, "alice")["status"] == "error"
    assert ex.execute(grand, sign(grand), req, "alice")["status"] == "error"


def test_existing_refusals_still_hold():
    ex = Executor()
    cap, sig = mkcap([{"type": "data", "resource": "/data/w", "method": "GET"}])
    req = {"type": "data", "resource": "/data/w", "method": "GET"}
    tampered = dict(cap)
    tampered["rights"] = [{"type": "data", "resource": "/data/w", "method": "POST"}]
    assert ex.execute(tampered, sig, req, "alice")["status"] == "error"
    assert ex.execute(cap, sig, req, "mallory")["status"] == "error"
    assert ex.execute(cap, sig, req, "alice")["status"] == "ok"


if __name__ == "__main__":
    test_method_confusion_refused()
    test_rate_limit_survives_attenuation()
    test_revocation_cascades_to_children()
    test_existing_refusals_still_hold()
    print("all lineage security tests passed")
