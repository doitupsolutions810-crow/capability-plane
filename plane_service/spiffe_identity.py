"""SPIFFE / SPIRE Workload API identity (Track 2)."""
from __future__ import annotations
import os, socket
from dataclasses import dataclass
from typing import Optional, Set

@dataclass
class WorkloadIdentity:
    spiffe_id: str
    trust_domain: str
    source: str
    socket_reachable: bool = False

def _parse_trust_domain(spiffe_id: str) -> str:
    if not spiffe_id.startswith("spiffe://"):
        return os.environ.get("PLANE_TRUST_DOMAIN", "prod")
    return spiffe_id[len("spiffe://"):].split("/", 1)[0] or "prod"

def _socket_path(raw: Optional[str]) -> Optional[str]:
    if not raw: return None
    return raw[len("unix://"):] if raw.startswith("unix://") else raw

def _probe_socket(path: str) -> bool:
    if not os.path.exists(path): return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1.0); s.connect(path); s.close(); return True
    except Exception:
        return False

def _allowed_trust_domains() -> Set[str]:
    raw = os.environ.get("PLANE_ALLOWED_TRUST_DOMAINS", "")
    if not raw:
        return {os.environ.get("PLANE_TRUST_DOMAIN", "prod")}
    return {x.strip() for x in raw.split(",") if x.strip()}

def _try_workload_api(sock_path: str) -> Optional[WorkloadIdentity]:
    reachable = _probe_socket(sock_path)
    try:
        from spiffe import WorkloadApiClient
        with WorkloadApiClient(socket_path=sock_path) as client:
            svid = client.fetch_x509_svid()
            sid = str(svid.spiffe_id)
            td = _parse_trust_domain(sid)
            if td not in _allowed_trust_domains():
                return None
            return WorkloadIdentity(sid, td, "workload-api", socket_reachable=True)
    except ImportError:
        if reachable:
            print(f"[spiffe] socket reachable at {sock_path}; pip install spiffe")
    except Exception as e:
        print(f"[spiffe] {e}")
    return None

def fetch_workload_identity(socket_path: Optional[str] = None, trust_domain_cfg: Optional[str] = None) -> WorkloadIdentity:
    sock = _socket_path(socket_path or os.environ.get("SPIFFE_ENDPOINT_SOCKET"))
    env_id = os.environ.get("PLANE_SPIFFE_ID") or os.environ.get("SPIFFE_ID")
    if sock:
        ident = _try_workload_api(sock)
        if ident: return ident
        reachable = _probe_socket(sock)
        if env_id:
            return WorkloadIdentity(env_id, trust_domain_cfg or _parse_trust_domain(env_id), "env", socket_reachable=reachable)
    if env_id:
        return WorkloadIdentity(env_id, trust_domain_cfg or _parse_trust_domain(env_id), "env")
    td = trust_domain_cfg or os.environ.get("PLANE_TRUST_DOMAIN", "prod")
    return WorkloadIdentity(f"spiffe://{td}/agent/dev", td, "fallback")

def identity_summary() -> dict:
    ident = fetch_workload_identity()
    return {"spiffe_id": ident.spiffe_id, "trust_domain": ident.trust_domain, "source": ident.source,
            "socket_reachable": ident.socket_reachable, "socket_env": os.environ.get("SPIFFE_ENDPOINT_SOCKET")}
