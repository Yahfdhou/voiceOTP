"""Paramètres globaux gateway (maintenance, préfixes pays, etc.)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from db import DB_PATH

DEFAULT_MAINTENANCE_DETAIL = "Gateway is under scheduled maintenance"
DEFAULT_PREFIXES = ["222"]

_CREATE = """
CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    is_maintenance INTEGER NOT NULL DEFAULT 0,
    maintenance_detail TEXT,
    allowed_country_prefixes TEXT,
    updated_at TEXT
);
"""


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_prefixes(raw):
    if raw is None:
        return list(DEFAULT_PREFIXES)
    if isinstance(raw, list):
        items = [str(x).strip().lstrip("+") for x in raw if str(x).strip()]
        return items or list(DEFAULT_PREFIXES)
    text = str(raw or "").strip()
    if not text:
        return list(DEFAULT_PREFIXES)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            items = [str(x).strip().lstrip("+") for x in data if str(x).strip()]
            return items or list(DEFAULT_PREFIXES)
    except Exception:
        pass
    items = [p.strip().lstrip("+") for p in text.replace(";", ",").split(",") if p.strip()]
    return items or list(DEFAULT_PREFIXES)


def init_settings():
    with _connect() as conn:
        conn.executescript(_CREATE)
        cols = {item[1] for item in conn.execute("PRAGMA table_info(system_settings)").fetchall()}
        if "allowed_country_prefixes" not in cols:
            conn.execute("ALTER TABLE system_settings ADD COLUMN allowed_country_prefixes TEXT")
        row = conn.execute("SELECT id FROM system_settings WHERE id = 1").fetchone()
        if not row:
            conn.execute(
                """
                INSERT INTO system_settings
                (id, is_maintenance, maintenance_detail, allowed_country_prefixes)
                VALUES (1, 0, ?, ?)
                """,
                (DEFAULT_MAINTENANCE_DETAIL, json.dumps(DEFAULT_PREFIXES)),
            )
        else:
            current = conn.execute(
                "SELECT allowed_country_prefixes FROM system_settings WHERE id = 1"
            ).fetchone()
            if current and not (current["allowed_country_prefixes"] or "").strip():
                conn.execute(
                    "UPDATE system_settings SET allowed_country_prefixes = ? WHERE id = 1",
                    (json.dumps(DEFAULT_PREFIXES),),
                )


def get_settings():
    init_settings()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM system_settings WHERE id = 1").fetchone()
    if not row:
        return {
            "is_maintenance": False,
            "maintenance_detail": DEFAULT_MAINTENANCE_DETAIL,
            "allowed_country_prefixes": list(DEFAULT_PREFIXES),
            "updated_at": None,
        }
    return {
        "is_maintenance": bool(row["is_maintenance"]),
        "maintenance_detail": row["maintenance_detail"] or DEFAULT_MAINTENANCE_DETAIL,
        "allowed_country_prefixes": _parse_prefixes(row["allowed_country_prefixes"]),
        "updated_at": row["updated_at"],
    }


def update_settings(
    is_maintenance=None,
    maintenance_detail=None,
    allowed_country_prefixes=None,
):
    init_settings()
    current = get_settings()
    enabled = current["is_maintenance"] if is_maintenance is None else bool(is_maintenance)
    message = (
        (maintenance_detail or "").strip()
        if maintenance_detail is not None
        else current["maintenance_detail"]
    ) or DEFAULT_MAINTENANCE_DETAIL
    prefixes = (
        _parse_prefixes(allowed_country_prefixes)
        if allowed_country_prefixes is not None
        else current["allowed_country_prefixes"]
    )
    ts = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE system_settings
            SET is_maintenance = ?, maintenance_detail = ?,
                allowed_country_prefixes = ?, updated_at = ?
            WHERE id = 1
            """,
            (1 if enabled else 0, message, json.dumps(prefixes), ts),
        )
    return get_settings()


def set_maintenance(enabled: bool, detail: str | None = None):
    return update_settings(is_maintenance=enabled, maintenance_detail=detail)


def is_maintenance() -> bool:
    return bool(get_settings().get("is_maintenance"))


def global_country_prefixes():
    return list(get_settings().get("allowed_country_prefixes") or DEFAULT_PREFIXES)
