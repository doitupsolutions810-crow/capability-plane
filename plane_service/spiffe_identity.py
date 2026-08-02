"""SPIFFE / SPIRE Workload API identity."""
from __future__ import annotations
import os, socket
from dataclasses import dataclass
from typing import Optional

@dataclass
class WorkloadIdentity:
    spiffe_id: str
    trust_domain: str
    source: str

def _parse_trust_domain(spiffe_id: str) -> str:
    if not spiffe_id.startswith("spiffe://"):
        return os.environ.get("PLANE_TRUST_DOMAIN", "prod")
    return spiffe_id[len("spiffe://"):].split("/", 1)[0] or "prod"

def _socket_path(raw: Optional[str]) -> Optional[str]:
    if not raw: return None
    return raw[len("unix://"):] if raw.startswith("unix://") else raw

def _try_workload_api(sock_path: str) -> Optional[WorkloadIdentity]:
    try:
        from spiffe import WorkloadApiClient
        with WorkloadApiClient(socket_path=sock_path) as client:
            svid = client.fetch_x509_svid()
            sid = str(svid.spiffe_id)
            return WorkloadIdentity(sid, _parse_trust_domain(sid), "workload-api")
    except ImportError:
        pass
    except Exception as e:
        print(f"[spiffe] {e}")
    if os.path.exists(sock_path):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1.0); s.connect(sock_path); s.close()
            print(f"[spiffe] socket reachable at {sock_path}")
        except Exception as e:
            print(f"[spiffe] {e}")
    return None

def fetch_workload_identity(socket_path: Optional[str] = None, trust_domain_cfg: Optional[str] = None) -> WorkloadIdentity:
    env_id = os.environ.get("PLANE_SPIFFE_ID") or os.environ.get("SPIFFE_ID")
    sock = _socket_path(socket_path or os.environ.get("SPIFFE_ENDPOINT_SOCKET"))
    if sock:
        ident = _try_workload_api(sock)
        if ident: return ident
    if env_id:
        return WorkloadIdentity(env_id, trust_domain_cfg or _parse_trust_domain(env_id), "env")
    td = trust_domain_cfg or os.environ.get("PLANE_TRUST_DOMAIN", "prod")
    return WorkloadIdentity(f"spiffe://{td}/agent/dev", td, "fallback")
