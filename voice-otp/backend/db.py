import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "otp_history.db"

_CREATE = """
CREATE TABLE IF NOT EXISTS otp_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    destination TEXT NOT NULL,
    status TEXT NOT NULL,
    source_ip TEXT
);
CREATE INDEX IF NOT EXISTS idx_otp_events_timestamp ON otp_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_otp_events_user ON otp_events(user_id);
CREATE INDEX IF NOT EXISTS idx_otp_events_channel ON otp_events(channel);
CREATE INDEX IF NOT EXISTS idx_otp_events_status ON otp_events(status);
"""


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_partner_column(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(otp_events)").fetchall()}
    if "partner_id" not in cols:
        conn.execute("ALTER TABLE otp_events ADD COLUMN partner_id INTEGER")
    if "is_test" not in cols:
        conn.execute("ALTER TABLE otp_events ADD COLUMN is_test INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_otp_events_partner ON otp_events(partner_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_otp_events_is_test ON otp_events(is_test)"
    )


def init_db():
    with _connect() as conn:
        conn.executescript(_CREATE)
        _ensure_partner_column(conn)
    from partners import init_partners
    from system_settings import init_settings

    init_partners()
    init_settings()


def mask_destination(value, channel=None):
    raw = (value or "").strip()
    channel = (channel or "").strip().lower()
    if channel == "voice":
        digits = re.sub(r"\D", "", raw) or "1000"
        return f"ext {digits}"
    if not raw:
        return ""
    if "***" in raw:
        return raw
    if "@" in raw:
        local, _, domain = raw.partition("@")
        keep = local[:3] if len(local) >= 3 else (local[:1] or "*")
        return f"{keep}***@{domain.lower()}"
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return "***"
    if len(digits) <= 4:
        return f"ext {digits}"
    if digits.startswith("222") and len(digits) >= 7:
        national = digits[3:]
        return f"+222 {national[:2]}***{national[-2:]}"
    if len(digits) >= 8:
        return f"+{digits[:3]} {digits[3:5]}***{digits[-2:]}"
    return f"+{digits[:2]}***{digits[-2:]}"


def log_event(user_id, channel, destination, status, source_ip, partner_id=None, is_test=False):
    init_db()
    ts = datetime.now(timezone.utc).isoformat()
    pid = None
    try:
        if partner_id is not None and str(partner_id).strip() != "":
            pid = int(partner_id)
    except (TypeError, ValueError):
        pid = None
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO otp_events
            (timestamp, user_id, channel, destination, status, source_ip, partner_id, is_test)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                (user_id or "").strip() or "unknown",
                (channel or "unknown").strip().lower(),
                mask_destination(destination, channel),
                (status or "unknown").strip().lower(),
                (source_ip or "").strip(),
                pid,
                1 if is_test else 0,
            ),
        )


def last_request_context(user_id, partner_id=None, is_test=None):
    init_db()
    clauses = ["user_id = ?"]
    args = [(user_id or "").strip()]
    if partner_id is not None:
        clauses.append("partner_id = ?")
        args.append(int(partner_id))
    if is_test is not None:
        clauses.append("IFNULL(is_test, 0) = ?")
        args.append(1 if is_test else 0)
    sql = (
        "SELECT channel, destination FROM otp_events WHERE "
        + " AND ".join(clauses)
        + " ORDER BY id DESC LIMIT 1"
    )
    with _connect() as conn:
        row = conn.execute(sql, args).fetchone()
    if not row:
        return {"channel": "unknown", "destination": ""}
    return {"channel": row["channel"], "destination": row["destination"]}


def event_to_dict(row, extra=True):
    item = {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "user_id": row["user_id"],
        "channel": row["channel"],
        "status": row["status"],
        "destination": row["destination"],
        "source_ip": row["source_ip"],
    }
    try:
        keys = row.keys()
        if "is_test" in keys:
            item["is_test"] = bool(row["is_test"])
        if extra and "partner_id" in keys:
            item["partner_id"] = row["partner_id"]
    except Exception:
        pass
    return item


def count_events():
    init_db()
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM otp_events").fetchone()[0]


def counts_by_channel_and_status():
    init_db()
    with _connect() as conn:
        channels = conn.execute(
            "SELECT channel, COUNT(*) AS n FROM otp_events GROUP BY channel"
        ).fetchall()
        statuses = conn.execute(
            "SELECT status, COUNT(*) AS n FROM otp_events GROUP BY status"
        ).fetchall()
    return (
        {row["channel"]: row["n"] for row in channels},
        {row["status"]: row["n"] for row in statuses},
    )


def success_rate_24h():
    init_db()
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM otp_events WHERE timestamp >= ?",
            (since,),
        ).fetchone()[0]
        verified = conn.execute(
            "SELECT COUNT(*) FROM otp_events WHERE timestamp >= ? AND status = 'verified'",
            (since,),
        ).fetchone()[0]
    if total == 0:
        return 0.0
    return round((verified / total) * 100, 1)


def recent_events(limit=20):
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, timestamp, user_id, channel, destination, status, source_ip
            FROM otp_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [event_to_dict(r) for r in rows]


def _status_to_http(status: str) -> int:
    key = (status or "").lower()
    if key in ("sent", "verified", "ok"):
        return 200
    if key in ("expired", "invalid", "failed", "invalid_destination_country"):
        return 400
    if key in ("unauthorized", "account_revoked", "channel_disabled_for_account", "ip_unauthorized"):
        return 403
    if key in ("quota_exceeded", "too_many_attempts"):
        return 429
    if key in ("system_maintenance",):
        return 503
    return 200


def _traffic_row(row):
    status = row["status"]
    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "partner_id": row["partner_id"],
        "partner_name": row["partner_name"]
        or ("—" if not row["partner_id"] else f"#{row['partner_id']}"),
        "user_id": row["user_id"],
        "channel": row["channel"],
        "destination": row["destination"],
        "status": status,
        "status_code": _status_to_http(status),
        "source_ip": row["source_ip"] or "",
        "is_test": bool(row["is_test"]),
    }


def _traffic_summary(items):
    by_channel = {}
    by_status = {}
    test_count = 0
    live_count = 0
    success = 0
    failed = 0
    ips = set()
    for item in items:
        ch = item.get("channel") or "unknown"
        st = item.get("status") or "unknown"
        by_channel[ch] = by_channel.get(ch, 0) + 1
        by_status[st] = by_status.get(st, 0) + 1
        if item.get("is_test"):
            test_count += 1
        else:
            live_count += 1
        if st in ("sent", "verified", "ok"):
            success += 1
        elif st in (
            "failed", "invalid", "expired", "too_many_attempts",
            "invalid_destination_country", "channel_disabled_for_account",
            "ip_unauthorized",
        ):
            failed += 1
        ip = (item.get("source_ip") or "").strip()
        if ip:
            ips.add(ip)
    total = len(items)
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "success_rate": round((success / total) * 100, 1) if total else 0.0,
        "test_count": test_count,
        "live_count": live_count,
        "unique_ips": len(ips),
        "by_channel": by_channel,
        "by_status": by_status,
        "top_ips": sorted(ips)[:8],
    }


def live_traffic(limit=20, include_test=True, partner_id=None):
    """Derniers événements OTP avec nom partenaire (feed admin)."""
    init_db()
    try:
        limit = min(max(int(limit or 20), 1), 100)
    except (TypeError, ValueError):
        limit = 20
    clauses = []
    args = []
    if not include_test:
        clauses.append("IFNULL(e.is_test, 0) = 0")
    if partner_id is not None and str(partner_id).strip() != "":
        try:
            clauses.append("e.partner_id = ?")
            args.append(int(partner_id))
        except (TypeError, ValueError):
            pass
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    args.append(limit)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT e.id, e.timestamp, e.user_id, e.channel, e.destination,
                   e.status, e.source_ip, e.partner_id, IFNULL(e.is_test, 0) AS is_test,
                   p.name AS partner_name
            FROM otp_events e
            LEFT JOIN partner_accounts p ON p.id = e.partner_id
            {where}
            ORDER BY e.id DESC
            LIMIT ?
            """,
            tuple(args),
        ).fetchall()
        partner_rows = conn.execute(
            """
            SELECT p.id, p.name, COUNT(e.id) AS event_count
            FROM partner_accounts p
            LEFT JOIN otp_events e ON e.partner_id = p.id
            GROUP BY p.id, p.name
            ORDER BY event_count DESC, p.name COLLATE NOCASE
            """
        ).fetchall()
    items = [_traffic_row(row) for row in rows]
    partners = [
        {
            "id": row["id"],
            "name": row["name"],
            "event_count": int(row["event_count"] or 0),
        }
        for row in partner_rows
    ]
    return {
        "results": items,
        "summary": _traffic_summary(items),
        "partners": partners,
        "partner_id": int(partner_id) if partner_id not in (None, "") else None,
        "limit": limit,
    }


def query_events(channel=None, status=None, date_from=None, date_to=None, page=1, page_size=20):
    init_db()
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    clauses = []
    args = []
    if channel:
        clauses.append("channel = ?")
        args.append(channel.strip().lower())
    if status:
        clauses.append("status = ?")
        args.append(status.strip().lower())
    if date_from:
        clauses.append("timestamp >= ?")
        args.append(date_from)
    if date_to:
        clauses.append("timestamp <= ?")
        args.append(date_to)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM otp_events {where}",
            args,
        ).fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT id, timestamp, user_id, channel, destination, status, source_ip
            FROM otp_events
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            [*args, page_size, offset],
        ).fetchall()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [event_to_dict(r) for r in rows],
    }


CHANNELS = ("voice", "sms", "whatsapp", "email")
STATUSES = ("sent", "failed", "verified", "invalid", "expired", "too_many_attempts")


def _parse_ts(value):
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except Exception:
        return None


def _int(value, default, lo, hi):
    try:
        return min(max(int(value), lo), hi)
    except (TypeError, ValueError):
        return default


def _since(hours=None, days=None):
    now = datetime.now(timezone.utc)
    if days is not None:
        return now - timedelta(days=days)
    return now - timedelta(hours=hours or 24)


def _load_events_since(start):
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, user_id, channel, status
            FROM otp_events
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (start.isoformat(),),
        ).fetchall()
    events = []
    for row in rows:
        ts = _parse_ts(row["timestamp"])
        if ts is None:
            continue
        events.append({
            "timestamp": ts,
            "user_id": row["user_id"],
            "channel": row["channel"],
            "status": row["status"],
        })
    return events


def _count_status(events, status):
    return sum(1 for e in events if e["status"] == status)


def _rate(part, total):
    if not total:
        return 0.0
    return round((part / total) * 100, 1)


def overview_kpis():
    now = datetime.now(timezone.utc)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    ev_24h = _load_events_since(_since(hours=24))
    ev_7d = _load_events_since(_since(days=7))
    ev_today = [e for e in ev_24h if e["timestamp"] >= start_today]
    verified_24h = _count_status(ev_24h, "verified")
    sent_24h = _count_status(ev_24h, "sent")
    failed_24h = _count_status(ev_24h, "failed")
    invalid_24h = _count_status(ev_24h, "invalid")
    verified_7d = _count_status(ev_7d, "verified")
    return {
        "generated_at": now.isoformat(),
        "total_requests": count_events(),
        "today": len(ev_today),
        "last_24h": len(ev_24h),
        "last_7d": len(ev_7d),
        "sent_24h": sent_24h,
        "verified_24h": verified_24h,
        "failed_24h": failed_24h,
        "invalid_24h": invalid_24h,
        "success_rate_24h": _rate(verified_24h, len(ev_24h)),
        "success_rate_7d": _rate(verified_7d, len(ev_7d)),
        "verify_rate_24h": _rate(verified_24h, sent_24h),
        "unique_users_7d": len({e["user_id"] for e in ev_7d}),
        "avg_per_day_7d": round(len(ev_7d) / 7, 1),
    }


def timeseries(days=7, granularity="day"):
    days = _int(days, 7, 1, 90)
    granularity = "hour" if str(granularity).lower() == "hour" else "day"
    start = _since(days=days)
    events = _load_events_since(start)
    now = datetime.now(timezone.utc)
    buckets = []
    cursor = start.replace(minute=0, second=0, microsecond=0)
    if granularity == "day":
        cursor = cursor.replace(hour=0)
    step = timedelta(hours=1) if granularity == "hour" else timedelta(days=1)
    fmt = "%Y-%m-%dT%H:00:00" if granularity == "hour" else "%Y-%m-%d"
    counts = {}
    while cursor <= now:
        key = cursor.strftime(fmt)
        counts[key] = {"label": key, "total": 0, "sent": 0, "verified": 0, "failed": 0, "invalid": 0}
        cursor += step
        buckets.append(key)
    for event in events:
        key = event["timestamp"].strftime(fmt)
        if key not in counts:
            continue
        counts[key]["total"] += 1
        if event["status"] in counts[key]:
            counts[key][event["status"]] += 1
    return {
        "granularity": granularity,
        "days": days,
        "points": [counts[key] for key in buckets],
    }


def channel_stats(days=7):
    days = _int(days, 7, 1, 90)
    events = _load_events_since(_since(days=days))
    items = []
    for channel in CHANNELS:
        subset = [e for e in events if e["channel"] == channel]
        verified = _count_status(subset, "verified")
        sent = _count_status(subset, "sent")
        items.append({
            "channel": channel,
            "total": len(subset),
            "sent": sent,
            "verified": verified,
            "failed": _count_status(subset, "failed"),
            "success_rate": _rate(verified, len(subset)),
        })
    return {"days": days, "items": items}


def status_stats(days=7):
    days = _int(days, 7, 1, 90)
    events = _load_events_since(_since(days=days))
    items = []
    for status in STATUSES:
        n = _count_status(events, status)
        items.append({
            "status": status,
            "count": n,
            "percent": _rate(n, len(events)),
        })
    return {"days": days, "total": len(events), "items": items}


def heatmap(days=7):
    days = _int(days, 7, 1, 30)
    events = _load_events_since(_since(days=days))
    grid = [[0 for _ in range(24)] for _ in range(7)]
    for event in events:
        grid[event["timestamp"].weekday()][event["timestamp"].hour] += 1
    return {
        "days": days,
        "weekdays": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "hours": list(range(24)),
        "grid": grid,
        "max": max((max(row) for row in grid), default=0),
    }


def funnel(days=7):
    days = _int(days, 7, 1, 90)
    events = _load_events_since(_since(days=days))
    sent = _count_status(events, "sent")
    verified = _count_status(events, "verified")
    invalid = _count_status(events, "invalid")
    expired = _count_status(events, "expired")
    blocked = _count_status(events, "too_many_attempts")
    failed = _count_status(events, "failed")
    steps = [
        {"key": "sent", "label": "Codes envoyés", "count": sent},
        {"key": "verified", "label": "Vérifiés", "count": verified},
        {"key": "invalid", "label": "Codes invalides", "count": invalid},
        {"key": "expired", "label": "Expirés", "count": expired},
        {"key": "too_many_attempts", "label": "Bloqués", "count": blocked},
        {"key": "failed", "label": "Échecs d'envoi", "count": failed},
    ]
    return {
        "days": days,
        "conversion": _rate(verified, sent),
        "steps": steps,
    }


def top_users(days=7, limit=8):
    days = _int(days, 7, 1, 90)
    limit = _int(limit, 8, 1, 20)
    events = _load_events_since(_since(days=days))
    bag = {}
    for event in events:
        item = bag.setdefault(event["user_id"], {"user_id": event["user_id"], "total": 0, "verified": 0})
        item["total"] += 1
        if event["status"] == "verified":
            item["verified"] += 1
    ranked = sorted(bag.values(), key=lambda x: x["total"], reverse=True)[:limit]
    for item in ranked:
        item["success_rate"] = _rate(item["verified"], item["total"])
    return {"days": days, "items": ranked}


def sparkline_24h():
    start = _since(hours=24)
    events = _load_events_since(start)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    points = []
    for i in range(23, -1, -1):
        bucket = now - timedelta(hours=i)
        key = bucket.strftime("%H:00")
        n = sum(
            1
            for e in events
            if e["timestamp"].year == bucket.year
            and e["timestamp"].month == bucket.month
            and e["timestamp"].day == bucket.day
            and e["timestamp"].hour == bucket.hour
        )
        points.append({"hour": key, "total": n})
    return {"points": points, "peak": max((p["total"] for p in points), default=0)}


def _partner_balances_payload():
    from partners import partner_balances
    return partner_balances()


def dashboard_payload():
    by_channel, by_status = counts_by_channel_and_status()
    return {
        "kpis": overview_kpis(),
        "by_channel": by_channel,
        "by_status": by_status,
        "timeseries": timeseries(days=7, granularity="day"),
        "sparkline_24h": sparkline_24h(),
        "channels": channel_stats(days=7),
        "statuses": status_stats(days=7),
        "funnel": funnel(days=7),
        "heatmap": heatmap(days=7),
        "top_users": top_users(days=7, limit=8),
        "recent": recent_events(8),
        "partner_balances": _partner_balances_payload(),
    }


def partner_request_totals():
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT partner_id, COUNT(*) AS n
            FROM otp_events
            WHERE partner_id IS NOT NULL AND IFNULL(is_test, 0) = 0
            GROUP BY partner_id
            """
        ).fetchall()
    return {int(row["partner_id"]): int(row["n"]) for row in rows if row["partner_id"] is not None}


def partner_usage_stats(partner_id, days=14):
    try:
        partner_id = int(partner_id)
    except (TypeError, ValueError):
        partner_id = 0
    days = _int(days, 14, 1, 90)
    start = _since(days=days)
    start_24h = _since(hours=24)
    now = datetime.now(timezone.utc)
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, user_id, channel, status
            FROM otp_events
            WHERE partner_id = ? AND timestamp >= ? AND IFNULL(is_test, 0) = 0
            ORDER BY timestamp ASC
            """,
            (partner_id, start.isoformat()),
        ).fetchall()
        total_all = conn.execute(
            """
            SELECT COUNT(*) FROM otp_events
            WHERE partner_id = ? AND IFNULL(is_test, 0) = 0
            """,
            (partner_id,),
        ).fetchone()[0]
        tests_all = conn.execute(
            """
            SELECT COUNT(*) FROM otp_events
            WHERE partner_id = ? AND IFNULL(is_test, 0) = 1
            """,
            (partner_id,),
        ).fetchone()[0]
        tests_period = conn.execute(
            """
            SELECT COUNT(*) FROM otp_events
            WHERE partner_id = ? AND timestamp >= ? AND IFNULL(is_test, 0) = 1
            """,
            (partner_id, start.isoformat()),
        ).fetchone()[0]
        recent = conn.execute(
            """
            SELECT id, timestamp, user_id, channel, destination, status, source_ip, is_test
            FROM otp_events
            WHERE partner_id = ? AND IFNULL(is_test, 0) = 0
            ORDER BY id DESC
            LIMIT 12
            """,
            (partner_id,),
        ).fetchall()

    events = []
    for row in rows:
        ts = _parse_ts(row["timestamp"])
        if ts is None:
            continue
        events.append({
            "timestamp": ts,
            "user_id": row["user_id"],
            "channel": row["channel"],
            "status": row["status"],
        })

    ev_24h = [e for e in events if e["timestamp"] >= start_24h]
    sent = _count_status(events, "sent")
    verified = _count_status(events, "verified")
    failed = _count_status(events, "failed")
    invalid = _count_status(events, "invalid")

    fmt = "%Y-%m-%d"
    cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)
    counts = {}
    buckets = []
    while cursor <= now:
        key = cursor.strftime(fmt)
        counts[key] = {
            "label": key,
            "total": 0,
            "sent": 0,
            "verified": 0,
            "failed": 0,
            "invalid": 0,
        }
        buckets.append(key)
        cursor += timedelta(days=1)
    for event in events:
        key = event["timestamp"].strftime(fmt)
        if key not in counts:
            continue
        counts[key]["total"] += 1
        if event["status"] in counts[key]:
            counts[key][event["status"]] += 1

    channel_items = []
    for channel in CHANNELS:
        subset = [e for e in events if e["channel"] == channel]
        verified_ch = _count_status(subset, "verified")
        channel_items.append({
            "channel": channel,
            "total": len(subset),
            "sent": _count_status(subset, "sent"),
            "verified": verified_ch,
            "failed": _count_status(subset, "failed"),
            "success_rate": _rate(verified_ch, len(subset)),
        })

    status_items = []
    for status in STATUSES:
        n = _count_status(events, status)
        status_items.append({
            "status": status,
            "count": n,
            "percent": _rate(n, len(events)),
        })

    return {
        "partner_id": partner_id,
        "days": days,
        "kpis": {
            "total": int(total_all or 0),
            "period": len(events),
            "last_24h": len(ev_24h),
            "sent": sent,
            "verified": verified,
            "failed": failed,
            "invalid": invalid,
            "success_rate": _rate(verified, len(events)),
            "verify_rate": _rate(verified, sent),
            "unique_users": len({e["user_id"] for e in events}),
            "tests_count": int(tests_all or 0),
            "tests_period": int(tests_period or 0),
        },
        "timeseries": {
            "granularity": "day",
            "days": days,
            "points": [counts[key] for key in buckets],
        },
        "channels": {"days": days, "items": channel_items},
        "statuses": {"days": days, "total": len(events), "items": status_items},
        "recent": [event_to_dict(row) for row in recent],
    }


def cleanup_older_than_days(days=30):
    init_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM otp_events WHERE timestamp < ?", (cutoff,))
        return cur.rowcount


def _repair_voice_destinations():
    with _connect() as conn:
        conn.execute(
            """
            UPDATE otp_events
            SET destination = 'ext 1000'
            WHERE channel = 'voice'
              AND (destination = '****' OR destination = '1000')
            """
        )


init_db()
_repair_voice_destinations()
