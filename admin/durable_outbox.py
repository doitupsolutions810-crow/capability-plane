"""Durable outbox — SQLite local; Postgres schema for production (Track 1)."""
from __future__ import annotations
import json, os, sqlite3, time, uuid
from pathlib import Path
from typing import Any, Callable, List, Optional
from .outbox import OutboxEvent

def _default_db_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    p = Path(os.environ.get("OUTBOX_DB_PATH", str(root / "data" / "outbox.db")))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

class DurableOutbox:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path), timeout=30)
        c.row_factory = sqlite3.Row
        return c
    def _init_schema(self) -> None:
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS outbox_events (
                id TEXT PRIMARY KEY, aggregate_id TEXT NOT NULL, event_type TEXT NOT NULL,
                payload TEXT NOT NULL, created_at REAL NOT NULL, published_at REAL,
                attempt_count INTEGER NOT NULL DEFAULT 0, next_attempt_at REAL NOT NULL,
                last_error TEXT, UNIQUE(event_type, aggregate_id))""")
            c.commit()
    def enqueue(self, aggregate_id: str, event_type: str, payload: dict[str, Any]) -> OutboxEvent:
        eid, now = str(uuid.uuid4()), time.time()
        ev = OutboxEvent(id=eid, aggregate_id=aggregate_id, event_type=event_type, payload=payload, created_at=now, next_attempt_at=now)
        with self._conn() as c:
            try:
                c.execute("INSERT INTO outbox_events (id,aggregate_id,event_type,payload,created_at,next_attempt_at) VALUES (?,?,?,?,?,?)",
                    (eid, aggregate_id, event_type, json.dumps(payload), now, now))
                c.commit()
            except sqlite3.IntegrityError:
                row = c.execute("SELECT * FROM outbox_events WHERE event_type=? AND aggregate_id=?", (event_type, aggregate_id)).fetchone()
                if row: return self._row_to_event(row)
                raise
        return ev
    def _row_to_event(self, row) -> OutboxEvent:
        return OutboxEvent(id=row["id"], aggregate_id=row["aggregate_id"], event_type=row["event_type"],
            payload=json.loads(row["payload"]), created_at=row["created_at"], published_at=row["published_at"],
            attempt_count=row["attempt_count"], next_attempt_at=row["next_attempt_at"], last_error=row["last_error"])
    def claim_batch(self, limit: int = 50) -> List[OutboxEvent]:
        now = time.time()
        with self._conn() as c:
            rows = c.execute("SELECT * FROM outbox_events WHERE published_at IS NULL AND next_attempt_at<=? ORDER BY created_at LIMIT ?", (now, limit)).fetchall()
            return [self._row_to_event(r) for r in rows]
    def mark_published(self, event_id: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE outbox_events SET published_at=? WHERE id=?", (time.time(), event_id)); c.commit()
    def mark_failed(self, event_id: str, error: str, backoff_seconds: float = 5.0) -> None:
        with self._conn() as c:
            row = c.execute("SELECT attempt_count FROM outbox_events WHERE id=?", (event_id,)).fetchone()
            attempt = int(row["attempt_count"] if row else 0) + 1
            delay = min(300.0, backoff_seconds * (2 ** min(attempt, 6)))
            c.execute("UPDATE outbox_events SET attempt_count=?, next_attempt_at=?, last_error=? WHERE id=?", (attempt, time.time()+delay, error, event_id))
            c.commit()
    def unpublished_count(self) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) AS n FROM outbox_events WHERE published_at IS NULL").fetchone()["n"])
    def relay_once(self, publish_fn: Callable[[OutboxEvent], None]) -> int:
        n = 0
        for ev in self.claim_batch():
            try:
                publish_fn(ev); self.mark_published(ev.id); n += 1
            except Exception as e:
                self.mark_failed(ev.id, str(e))
        return n

def jetstream_publish_fn(subject_prefix: str = "admin.commands.v1"):
    def _publish(ev: OutboxEvent) -> None:
        print(f"[durable-outbox] publish {subject_prefix}.{ev.event_type} aggregate={ev.aggregate_id}")
        if os.environ.get("ATTESTPIPE_MIRROR_OUTBOX", "1") == "1":
            try:
                from attestpipe.bus import BUS
                BUS.publish({"message_type": "OutboxEventPublished", "event_type": ev.event_type,
                    "aggregate_id": ev.aggregate_id, "payload": ev.payload})
            except Exception as e:
                print(f"[durable-outbox] attestpipe skip: {e}")
    return _publish
