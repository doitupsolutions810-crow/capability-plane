"""Unified plane configuration loader (dev-friendly)."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pip install pyyaml")
    with path.open() as f:
        return yaml.safe_load(f) or {}


def load_profile(name: str | None = None) -> dict[str, Any]:
    name = name or os.environ.get("PLANE_PROFILE", "dev")
    path = ROOT / "config" / f"mesh_profile_{name}.yaml"
    profile = load_yaml(path)
    floci_env = ROOT / "config" / "floci.env"
    if floci_env.exists():
        for line in floci_env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    return profile


def cloud_endpoint(profile: dict[str, Any]) -> str | None:
    cloud = profile.get("cloud") or {}
    return cloud.get("endpoint_url") or os.environ.get("AWS_ENDPOINT_URL")


if __name__ == "__main__":
    p = load_profile("dev")
    print("profile:", p.get("name"))
    print("production:", p.get("production"))
    print("endpoint:", cloud_endpoint(p))
