"""Ed25519 capability signing (production-shaped)."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

_KEY: Optional[Ed25519PrivateKey] = None
_PUB: Optional[Ed25519PublicKey] = None


def canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _load_or_create_key() -> Ed25519PrivateKey:
    global _KEY, _PUB
    if _KEY is not None:
        return _KEY
    key_path = Path(os.environ.get("PLANE_SIGNING_KEY", "config/broker_ed25519.pem"))
    if key_path.exists():
        data = key_path.read_bytes()
        _KEY = serialization.load_pem_private_key(data, password=None)  # type: ignore
    else:
        _KEY = Ed25519PrivateKey.generate()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        pem = _KEY.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_path.write_bytes(pem)
        key_path.with_suffix(".pub.pem").write_bytes(
            _KEY.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    _PUB = _KEY.public_key()
    return _KEY


def sign(cap: dict[str, Any]) -> str:
    key = _load_or_create_key()
    return base64.b64encode(key.sign(canonical(cap))).decode()


def verify_sig(cap: dict[str, Any], sig_b64: str) -> bool:
    _load_or_create_key()
    assert _PUB is not None
    try:
        _PUB.verify(base64.b64decode(sig_b64), canonical(cap))
        return True
    except Exception:
        return False


def public_key_b64() -> str:
    _load_or_create_key()
    assert _PUB is not None
    raw = _PUB.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode()
