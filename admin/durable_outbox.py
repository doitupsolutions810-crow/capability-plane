"""SQLite transactional outbox: durable intent and lease-fenced at-least-once delivery.

A marked-published record means an explicitly injected publisher acknowledged delivery.
An unknown result is retried and requires downstream idempotency by event id.
This module is self-contained because the original repository lacks admin/outbox.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import json
import math
import os
import re
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Optional
import uuid


class OutboxError(RuntimeError):
    pass


class OutboxConflict(OutboxError):
    """Same logical operation key used with a different payload."""


class OutboxLeaseLost(OutboxError):
    """An expired or superseded relay may not finish a claimed operation."""


@dataclass(frozen=True)
class OutboxEvent:
    id: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: float
    published_at: float | None = None
    attempt_count: int = 0
    next_attempt_at: float = 0.0
    last_error: str | None = None
    claim_token: str | None = None
    lease_until: float | None = None


def _default_db_path() -> Path:
    return Path(os.environ.get("OUTBOX_DB_PATH", str(Path(__file__).resolve().parents[1] / "data" / "outbox.db")))


def _name(value: str, label: str) -> str:
    if not isinstance(value, str) or not 0 < len(value.strip()) <= 128 or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} must be a nonempty bounded label")
    return value


def _canonical(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    try:
        raw = json.dumps(payload, allow_nan=False, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        raise ValueError("payload is not valid finite JSON") from exc
    if len(raw.encode("utf-8")) > 65_536:
        raise ValueError("payload exceeds 64 KiB")
    return raw


def _row_event(row: sqlite3.Row) -> OutboxEvent:
    try:
        data = json.loads(row["payload"], parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        _canonical(data)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise OutboxError("stored outbox payload is corrupt") from exc
    return OutboxEvent(id=row["id"], aggregate_id=row["aggregate_id"], event_type=row["event_type"],
                       payload=data, created_at=row["created_at"], published_at=row["published_at"],
                       attempt_count=row["attempt_count"], next_attempt_at=row["next_attempt_at"],
                       last_error=row["last_error"], claim_token=row["claim_token"], lease_until=row["lease_until"])


class DurableOutbox:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(str(self.db_path), timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000")
        try:
            with c:
                yield c
        finally:
            c.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("""CREATE TABLE IF NOT EXISTS outbox_events (
                id TEXT PRIMARY KEY, aggregate_id TEXT NOT NULL, event_type TEXT NOT NULL,
                payload TEXT NOT NULL, created_at REAL NOT NULL, published_at REAL,
                attempt_count INTEGER NOT NULL DEFAULT 0, next_attempt_at REAL NOT NULL,
                last_error TEXT, UNIQUE(event_type, aggregate_id))""")
            existing = {row["name"] for row in c.execute("PRAGMA table_info(outbox_events)")}
            if "claim_token" not in existing:
                c.execute("ALTER TABLE outbox_events ADD COLUMN claim_token TEXT")
            if "lease_until" not in existing:
                c.execute("ALTER TABLE outbox_events ADD COLUMN lease_until REAL")

    def enqueue(self, aggregate_id: str, event_type: str, payload: dict[str, Any]) -> OutboxEvent:
        aggregate_id, event_type = _name(aggregate_id, "aggregate_id"), _name(event_type, "event_type")
        raw, now, eid = _canonical(payload), time.time(), uuid.uuid4().hex
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM outbox_events WHERE event_type=? AND aggregate_id=?", (event_type, aggregate_id)).fetchone()
            if row is not None:
                ev = _row_event(row)
                if _canonical(ev.payload) != raw:
                    raise OutboxConflict("idempotency key replayed with changed payload")
                return ev
            c.execute("INSERT INTO outbox_events(id, aggregate_id, event_type, payload, created_at, next_attempt_at) VALUES(?,?,?,?,?,?)",
                      (eid, aggregate_id, event_type, raw, now, now))
            row = c.execute("SELECT * FROM outbox_events WHERE id=?", (eid,)).fetchone()
            return _row_event(row)

    def claim_batch(self, limit: int = 50, lease_seconds: float = 30.0) -> list[OutboxEvent]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be integer 1..1000")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (float, int)) or not math.isfinite(lease_seconds) or not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be finite in 1..3600")
        now = time.time()
        out = []
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            rows = c.execute("""SELECT * FROM outbox_events WHERE published_at IS NULL
                                  AND next_attempt_at<=? AND (lease_until IS NULL OR lease_until<=?)
                                  ORDER BY created_at, id LIMIT ?""", (now, now, limit)).fetchall()
            for row in rows:
                token = uuid.uuid4().hex
                c.execute("UPDATE outbox_events SET claim_token=?, lease_until=? WHERE id=?",
                          (token, now + lease_seconds, row["id"]))
                new = c.execute("SELECT * FROM outbox_events WHERE id=?", (row["id"],)).fetchone()
                out.append(_row_event(new))
        return out

    def _finalize(self, event_id: str, claim_token: str | None, success: bool, error: str = "", backoff_seconds: float = 5.0) -> bool:
        if not isinstance(claim_token, str) or not claim_token:
            raise OutboxLeaseLost("claim token required")
        now = time.time()
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM outbox_events WHERE id=?", (event_id,)).fetchone()
            if row is None or row["published_at"] is not None or row["claim_token"] != claim_token or not isinstance(row["lease_until"], (float, int)) or row["lease_until"] <= now:
                raise OutboxLeaseLost("claim is expired, absent, or superseded")
            if success:
                c.execute("UPDATE outbox_events SET published_at=?, claim_token=NULL, lease_until=NULL, last_error=NULL WHERE id=?",
                          (now, event_id))
            else:
                if isinstance(backoff_seconds, bool) or not isinstance(backoff_seconds, (float, int)) or not math.isfinite(backoff_seconds) or not 0 <= backoff_seconds <= 300:
                    raise ValueError("invalid retry backoff")
                attempts = int(row["attempt_count"]) + 1
                delay = min(300.0, backoff_seconds * 2 ** min(attempts, 6))
                c.execute("""UPDATE outbox_events SET attempt_count=?, next_attempt_at=?, last_error=?,
                            claim_token=NULL, lease_until=NULL WHERE id=?""",
                          (attempts, now + delay, error[:300], event_id))
        return True

    def mark_published(self, event_id: str, claim_token: str | None = None) -> bool:
        return self._finalize(event_id, claim_token, True)

    def mark_failed(self, event_id: str, error: str, backoff_seconds: float = 5.0,
                    claim_token: str | None = None) -> bool:
        return self._finalize(event_id, claim_token, False, error, backoff_seconds)

    def unpublished_count(self) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) FROM outbox_events WHERE published_at IS NULL").fetchone()[0])

    def relay_once(self, publish_fn: Callable[[OutboxEvent], Any], *, limit: int = 50) -> int:
        sent = 0
        for ev in self.claim_batch(limit=limit):
            try:
                outcome = publish_fn(ev)
                # Require affirmative acknowledgment. None, false and exceptions are unknown.
                if outcome is not True:
                    raise OutboxError("publisher returned no explicit acknowledgment")
                self.mark_published(ev.id, ev.claim_token)
                sent += 1
            except OutboxLeaseLost:
                # Another worker owns the operation. No finalization is permitted.
                continue
            except Exception as exc:
                try:
                    self.mark_failed(ev.id, type(exc).__name__ + ": " + str(exc), claim_token=ev.claim_token)
                except OutboxLeaseLost:
                    pass
        return sent


def jetstream_publish_fn(subject_prefix: str = "admin.commands.v1", *, transport: Callable[[str, dict], bool] | None = None):
    """No fake JetStream success. Inject an authenticated publisher that confirms ack."""
    if transport is None:
        raise OutboxError("JetStream transport is not configured; cannot claim delivery")
    _name(subject_prefix, "subject_prefix")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in subject_prefix.split(".")):
        raise OutboxError("invalid JetStream subject prefix")

    def _publish(ev: OutboxEvent) -> bool:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", ev.event_type):
            raise OutboxError("event type is unsafe as a JetStream subject token")
        return transport(subject_prefix + "." + ev.event_type,
                         {"event_id": ev.id, "aggregate_id": ev.aggregate_id,
                          "event_type": ev.event_type, "payload": ev.payload}) is True

    return _publish
