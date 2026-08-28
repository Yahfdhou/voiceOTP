from datetime import datetime, timedelta, timezone

from db import DB_PATH
import sqlite3

CHANNELS = ("sms", "whatsapp", "voice", "email")
STATUSES = ("sent", "failed", "verified", "invalid", "expired", "too_many_attempts")


def _parse(ts):
    try:
        return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except Exception:
        return None


def load_events(hours=48):
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT timestamp, channel, status
        FROM otp_events
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
        """,
        (start.isoformat(),),
    ).fetchall()
    conn.close()
    events = []
    for row in rows:
        ts = _parse(row["timestamp"])
        if ts is None:
            continue
        events.append({
            "timestamp": ts,
            "channel": (row["channel"] or "unknown").lower(),
            "status": (row["status"] or "unknown").lower(),
        })
    return events


def _rate(part, total):
    if not total:
        return 0.0
    return round((part / total) * 100, 1)


def _count(events, status=None, channel=None):
    n = 0
    for event in events:
        if channel and event["channel"] != channel:
            continue
        if status and event["status"] != status:
            continue
        n += 1
    return n


def channel_block(events, channel):
    subset = [e for e in events if e["channel"] == channel]
    total = len(subset)
    sent = _count(subset, "sent")
    verified = _count(subset, "verified")
    failed = _count(subset, "failed")
    invalid = _count(subset, "invalid")
    expired = _count(subset, "expired")
    blocked = _count(subset, "too_many_attempts")
    denom = verified + invalid + expired + blocked
    success = _rate(verified, denom if denom else total)
    failure = _rate(failed + invalid, total)
    reliability = round(max(0.0, min(100.0, 100 - failure + success * 0.15)), 1)
    return {
        "channel": channel,
        "requests": total,
        "sent": sent,
        "verified": verified,
        "failed": failed,
        "invalid": invalid,
        "expired": expired,
        "too_many_attempts": blocked,
        "success_rate": success,
        "failure_rate": failure,
        "reliability": min(100.0, reliability),
    }


def _channel_hourly_counts(events, channel, hours=24):
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    values = []
    for i in range(hours - 1, -1, -1):
        bucket = now - timedelta(hours=i)
        n = 0
        for event in events:
            ts = event["timestamp"]
            if event["channel"] != channel:
                continue
            if (
                ts.year == bucket.year
                and ts.month == bucket.month
                and ts.day == bucket.day
                and ts.hour == bucket.hour
            ):
                n += 1
        values.append(n)
    return values


def hourly_matrix(events, hours=24):
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    rows = []
    for i in range(hours - 1, -1, -1):
        bucket = now - timedelta(hours=i)
        subset = [
            e for e in events
            if e["timestamp"].year == bucket.year
            and e["timestamp"].month == bucket.month
            and e["timestamp"].day == bucket.day
            and e["timestamp"].hour == bucket.hour
        ]
        total = len(subset)
        failed = _count(subset, "failed")
        invalid = _count(subset, "invalid")
        blocked = _count(subset, "too_many_attempts")
        verified = _count(subset, "verified")
        rows.append({
            "hour": bucket.isoformat(),
            "requests": total,
            "failed": failed,
            "invalid": invalid,
            "too_many_attempts": blocked,
            "verified": verified,
            "failure_rate": _rate(failed + invalid, total),
            "success_rate": _rate(verified, total),
        })
    return rows


def build_features(hours=48):
    events = load_events(hours=hours)
    now = datetime.now(timezone.utc)
    last_1h = [e for e in events if e["timestamp"] >= now - timedelta(hours=1)]
    last_2h = [e for e in events if e["timestamp"] >= now - timedelta(hours=2)]
    last_6h = [e for e in events if e["timestamp"] >= now - timedelta(hours=6)]
    last_24h = [e for e in events if e["timestamp"] >= now - timedelta(hours=24)]
    prev_6h = [e for e in events if now - timedelta(hours=12) <= e["timestamp"] < now - timedelta(hours=6)]

    channels = {name: channel_block(last_24h, name) for name in CHANNELS}
    hourly = hourly_matrix(events, hours=min(hours, 48))

    total = len(last_24h)
    verified = _count(last_24h, "verified")
    failed = _count(last_24h, "failed")
    invalid = _count(last_24h, "invalid")
    blocked = _count(last_24h, "too_many_attempts")
    sent = _count(last_24h, "sent")

    channel_hourly = {
        name: _channel_hourly_counts(events, name, hours=24) for name in CHANNELS
    }

    return {
        "generated_at": now.isoformat(),
        "insufficient_data": total == 0,
        "ml_ready": total >= 5,
        "period": "last_24_hours",
        "totals": {
            "requests": total,
            "sent": sent,
            "verified": verified,
            "failed": failed,
            "invalid": invalid,
            "too_many_attempts": blocked,
            "success_rate": _rate(verified, total),
            "failure_rate": _rate(failed + invalid, total),
            "too_many_attempts_rate": _rate(blocked, total),
            "requests_last_hour": len(last_1h),
            "requests_last_2h": len(last_2h),
            "requests_per_hour": round(total / 24, 2),
        },
        "channels": channels,
        "channel_hourly": channel_hourly,
        "hourly": hourly,
        "trend_window": {
            "current_6h_failure": _rate(_count(last_6h, "failed") + _count(last_6h, "invalid"), len(last_6h)),
            "previous_6h_failure": _rate(_count(prev_6h, "failed") + _count(prev_6h, "invalid"), len(prev_6h)),
            "current_6h_success": _rate(_count(last_6h, "verified"), len(last_6h)),
            "previous_6h_success": _rate(_count(prev_6h, "verified"), len(prev_6h)),
            "current_6h_requests": len(last_6h),
            "previous_6h_requests": len(prev_6h),
        },
        "weekday": now.strftime("%A").lower(),
        "hour": now.hour,
    }


def llm_safe_context(features):
    channels = {}
    for name, block in (features.get("channels") or {}).items():
        channels[name] = {
            "requests": block["requests"],
            "success_rate": block["success_rate"],
            "failure_rate": block["failure_rate"],
            "reliability": block["reliability"],
        }
    totals = features.get("totals") or {}
    return {
        "period": features.get("period"),
        "insufficient_data": features.get("insufficient_data"),
        "sms": channels.get("sms", {}),
        "whatsapp": channels.get("whatsapp", {}),
        "voice": channels.get("voice", {}),
        "email": channels.get("email", {}),
        "totals": {
            "requests": totals.get("requests", 0),
            "success_rate": totals.get("success_rate", 0),
            "failure_rate": totals.get("failure_rate", 0),
            "too_many_attempts_rate": totals.get("too_many_attempts_rate", 0),
            "verified": totals.get("verified", 0),
            "failed": totals.get("failed", 0),
        },
        "trend_window": features.get("trend_window") or {},
    }
