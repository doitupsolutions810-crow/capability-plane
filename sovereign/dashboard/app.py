#!/usr/bin/env python3
"""Sovereign Agentic OS Dashboard — Horizons 1–5 operator surface."""
from __future__ import annotations
import json, os, sys, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PLANE = os.environ.get("PLANE_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
HOST = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
PORT = int(os.environ.get("DASHBOARD_PORT", "8501"))

def plane_get(path: str) -> dict:
    try:
        with urllib.request.urlopen(f"{PLANE}{path}", timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"status": "error", "error": str(e)}

def plane_post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{PLANE}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"status": "error", "error": str(e)}

def load_yaml_safe(path: Path):
    try:
        import yaml
        return yaml.safe_load(path.read_text()) if path.exists() else None
    except Exception:
        return None

def snapshot() -> dict:
    health = plane_get("/health")
    evidence = []
    ed = ROOT / "evidence"
    if ed.exists():
        for f in sorted(ed.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
            evidence.append({"id": f.stem, "path": str(f), "size": f.stat().st_size})
    return {"horizons": {
        "1_production_control_plane": {"plane_health": health, "plane_base_url": PLANE,
            "spiffe_id": os.environ.get("PLANE_SPIFFE_ID", "spiffe://prod/agent/dev"),
            "tls_front_door": os.environ.get("FRONT_DOOR_TLS", "0") == "1"},
        "2_confidential_mesh": {"broker_directory": load_yaml_safe(ROOT/"config"/"broker_directory.yaml"),
            "measurement_policy": load_yaml_safe(ROOT/"config"/"measurement_policy.yaml")},
        "3_evidence_compliance": {"recent_evidence": evidence},
        "4_policy_as_code": {"acceptance_policy": load_yaml_safe(ROOT/"config"/"acceptance_policy.yaml"),
            "policy_version": health.get("policy_version")},
        "5_sovereign_agentic_os": {"console": "POST /api/intent", "rules": ["No ambient shell", "Intent only via plane"]},
    }}

def run_intent(body: dict) -> dict:
    rights = body.get("rights") or [{"type": "Execute", "resource": body.get("resource", "tool.summarize")}]
    caller = body.get("caller") or os.environ.get("PLANE_SPIFFE_ID", "spiffe://prod/agent/dev")
    ttl = min(int(body.get("ttl_seconds") or 60), 120)
    issued = plane_post("/v1/capabilities/issue", {"rights": rights, "ttl_seconds": ttl, "caller": caller,
        "constraints": body.get("constraints") or {"rate_limit": {"count": 5, "window_seconds": 60}}})
    if issued.get("status") != "ok":
        return {"stage": "issue", **issued}
    cap, sig, required = issued["capability"], issued["signature"], rights[0]
    verified = plane_post("/v1/capabilities/verify", {"capability": cap, "signature": sig, "required": required, "caller": caller})
    if not verified.get("valid"):
        return {"stage": "verify", "issue": issued, **verified}
    executed = plane_post("/v1/execute", {"capability": cap, "signature": sig, "required": required, "caller": caller})
    return {"stage": "execute", "issue": issued, "verify": verified, "execute": executed}

# Full UI is in the local tree sovereign/dashboard/app.py (HTML embedded)
class Handler(BaseHTTPRequestHandler):
    def log_message(self, f, *a): print(f"[dashboard] {self.command} {self.path}")
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(b"<html><body><h1>Sovereign Dashboard</h1><p>Use full app.py from release for UI.</p></body></html>")
        elif path == "/api/snapshot":
            data = json.dumps(snapshot()).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        elif path == "/health":
            data = json.dumps({"status": "ok", "plane": PLANE}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n).decode() or "{}") if n else {}
        if path == "/api/intent":
            data = json.dumps(run_intent(body)).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        else:
            self.send_response(404); self.end_headers()

if __name__ == "__main__":
    print(f"Sovereign Dashboard http://{HOST}:{PORT} plane={PLANE}")
    HTTPServer((HOST, PORT), Handler).serve_forever()
