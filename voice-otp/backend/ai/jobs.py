import json
import sqlite3
import threading
import time
from datetime import datetime, timezone

from db import DB_PATH

_lock = threading.Lock()
_started = False

_CREATE = """
CREATE TABLE IF NOT EXISTS ai_snapshots (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_CREATE)
    return conn


def save_snapshot(payload):
    blob = json.dumps(payload, ensure_ascii=False)
    ts = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO ai_snapshots (id, updated_at, payload)
            VALUES (1, ?, ?)
            """,
            (ts, blob),
        )


def load_snapshot():
    with _connect() as conn:
        row = conn.execute("SELECT updated_at, payload FROM ai_snapshots WHERE id = 1").fetchone()
    if not row:
        return None
    try:
        data = json.loads(row[1])
    except Exception:
        return None
    data["cached_at"] = row[0]
    return data


def refresh_snapshot():
    from ai.engine import compute_control_center, enrich_with_llm

    payload = compute_control_center()
    save_snapshot(payload)
    try:
        payload = enrich_with_llm(payload)
        save_snapshot(payload)
    except Exception as exc:
        print(f"[AI] LLM enrich failed: {type(exc).__name__}")
    return payload


def get_control_center(force=False):
    if not force:
        cached = load_snapshot()
        if cached and cached.get("kpis") and "anomalies" in cached:
            return cached
    return refresh_snapshot()


def start_ai_worker(interval=300):
    global _started
    with _lock:
        if _started:
            return
        _started = True

    def loop():
        while True:
            try:
                refresh_snapshot()
            except Exception as exc:
                print(f"[AI] refresh failed: {type(exc).__name__}")
            time.sleep(interval)

    try:
        from ai.engine import compute_control_center
        save_snapshot(compute_control_center())
    except Exception as exc:
        print(f"[AI] initial refresh failed: {type(exc).__name__}")
    thread = threading.Thread(target=loop, name="ai-control-center", daemon=True)
    thread.start()
    print("[AI] Control Center worker started")
