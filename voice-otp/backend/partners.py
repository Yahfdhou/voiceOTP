import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from db import DB_PATH
from partner_config import PARTNER_KEYS

DEFAULT_GRANT_DAYS = 30
EXPIRING_SOON_DAYS = 7

PLANS = {
    "starter": {
        "label": "Starter",
        "channels": ["sms", "whatsapp", "email"],
        "daily_quota": 100,
    },
    "pro": {
        "label": "Pro",
        "channels": ["voice", "sms", "whatsapp", "email"],
        "daily_quota": 1000,
    },
    "business": {
        "label": "Business",
        "channels": ["voice", "sms", "whatsapp", "email"],
        "daily_quota": 5000,
    },
}

_CREATE = """
CREATE TABLE IF NOT EXISTS partner_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    plan TEXT NOT NULL,
    channels TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    test_key_hash TEXT,
    test_key_prefix TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    daily_quota INTEGER NOT NULL,
    used_today INTEGER NOT NULL DEFAULT 0,
    used_on TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_partner_status ON partner_accounts(status);
"""


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_key(raw):
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def generate_api_key():
    return "sk_live_" + secrets.token_hex(16)


def generate_test_key():
    return "sk_test_" + secrets.token_hex(16)


def _key_prefix(raw):
    return ((raw or "")[:18] + "…") if raw else ""


def _row_val(row, key, default=None):
    try:
        if key not in row.keys():
            return default
        value = row[key]
        return default if value is None else value
    except Exception:
        return default


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _date_only(value):
    raw = str(value or "").strip()
    return raw[:10] if len(raw) >= 10 else ""


def _add_days(day, days):
    base = datetime.strptime(_date_only(day) or _today(), "%Y-%m-%d").date()
    return (base + timedelta(days=int(days))).isoformat()


def _days_left(until_day):
    until = _date_only(until_day)
    if not until:
        return -1
    try:
        end = datetime.strptime(until, "%Y-%m-%d").date()
    except ValueError:
        return -1
    return (end - datetime.now(timezone.utc).date()).days


def _parse_grant_days(value, default=DEFAULT_GRANT_DAYS):
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = default
    return min(max(days, 1), 366)


def _access_meta(until_day, status="active"):
    until = _date_only(until_day)
    left = _days_left(until)
    if status != "active":
        state = "revoked"
    elif not until or left < 0:
        state = "expired"
    elif left <= EXPIRING_SOON_DAYS:
        state = "expiring"
    else:
        state = "ok"
    return {
        "access_until": until,
        "days_left": left,
        "access_state": state,
    }


def access_ok(partner):
    if not partner or partner.get("status") != "active":
        return False
    return (partner.get("access_state") or "ok") != "expired"


def _quota_balance(daily_quota, used_today, status="active"):
    cap = max(int(daily_quota or 0), 0)
    used = max(int(used_today or 0), 0)
    remaining = max(cap - used, 0)
    used_pct = round((used / cap) * 100, 1) if cap else 0.0
    remaining_pct = round((remaining / cap) * 100, 1) if cap else 0.0
    if status != "active":
        state = "revoked"
    elif remaining <= 0:
        state = "empty"
    elif remaining_pct <= 20:
        state = "low"
    else:
        state = "ok"
    return {
        "daily_quota": cap,
        "used_today": used,
        "remaining_today": remaining,
        "remaining_pct": remaining_pct,
        "quota_used_pct": used_pct,
        "quota_state": state,
    }


def _row_to_partner(row):
    if not row:
        return None
    channels = json.loads(row["channels"] or "[]")
    used_on = row["used_on"]
    used_today = int(row["used_today"] or 0)
    if used_on != _today():
        used_today = 0
    status = row["status"]
    balance = _quota_balance(row["daily_quota"], used_today, status)
    access = _access_meta(_row_val(row, "access_until"), status)
    allow_voice = bool(int(_row_val(row, "allow_voice") or 0))
    allow_sms = bool(int(_row_val(row, "allow_sms") or 0))
    allow_whatsapp = bool(int(_row_val(row, "allow_whatsapp") or 0))
    allow_email = bool(int(_row_val(row, "allow_email") or 0))
    if not any((allow_voice, allow_sms, allow_whatsapp, allow_email)) and channels:
        flags = _flags_from_channels(channels)
        allow_voice = bool(flags["allow_voice"])
        allow_sms = bool(flags["allow_sms"])
        allow_whatsapp = bool(flags["allow_whatsapp"])
        allow_email = bool(flags["allow_email"])
    else:
        channels = _channels_from_flags(allow_voice, allow_sms, allow_whatsapp, allow_email) or channels
    allowed_ip = (_row_val(row, "allowed_ip") or "").strip() or None
    prefixes = _parse_prefixes(_row_val(row, "allowed_prefixes"))
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"] or "",
        "plan": row["plan"],
        "channels": channels,
        "allow_voice": allow_voice,
        "allow_sms": allow_sms,
        "allow_whatsapp": allow_whatsapp,
        "allow_email": allow_email,
        "allowed_ip": allowed_ip,
        "allowed_prefixes": prefixes,
        "key_prefix": row["key_prefix"],
        "test_key_prefix": _row_val(row, "test_key_prefix") or "",
        "status": status,
        "daily_quota": balance["daily_quota"],
        "used_today": balance["used_today"],
        "remaining_today": balance["remaining_today"],
        "remaining_pct": balance["remaining_pct"],
        "quota_used_pct": balance["quota_used_pct"],
        "quota_state": balance["quota_state"],
        "access_started_at": _date_only(_row_val(row, "access_started_at")) or "",
        "access_until": access["access_until"],
        "days_left": access["days_left"],
        "access_state": access["access_state"],
        "created_at": row["created_at"],
        "last_used_at": row["last_used_at"],
    }


_CHANNEL_FLAGS = {
    "voice": "allow_voice",
    "sms": "allow_sms",
    "whatsapp": "allow_whatsapp",
    "email": "allow_email",
}

_UNSET = object()


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off", ""):
        return False
    return default


def channel_enabled(partner, channel):
    if not partner:
        return False
    flag = _CHANNEL_FLAGS.get(channel)
    if flag and flag in partner:
        return bool(partner.get(flag))
    return channel in (partner.get("channels") or [])


def ip_authorized(partner, client_ip):
    raw = ((partner or {}).get("allowed_ip") or "").strip()
    if not raw:
        return True
    allowed = [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]
    if not allowed:
        return True
    client = (client_ip or "").strip()
    if not client:
        return False
    return client in allowed


def destination_prefixes_for(partner):
    partner_prefixes = (partner or {}).get("allowed_prefixes") or []
    if partner_prefixes:
        return [str(p).strip().lstrip("+") for p in partner_prefixes if str(p).strip()]
    from system_settings import global_country_prefixes
    return global_country_prefixes()


def destination_country_ok(digits, partner=None):
    from product_config import VOICE_LOCAL_EXT

    phone = "".join(ch for ch in str(digits or "") if ch.isdigit())
    if not phone:
        return False
    if phone == str(VOICE_LOCAL_EXT or "1000"):
        return True
    prefixes = destination_prefixes_for(partner)
    for prefix in prefixes:
        if prefix and phone.startswith(prefix):
            return True
    return False


def _ensure_test_key_columns(conn):
    cols = {item[1] for item in conn.execute("PRAGMA table_info(partner_accounts)").fetchall()}
    if "test_key_hash" not in cols:
        conn.execute("ALTER TABLE partner_accounts ADD COLUMN test_key_hash TEXT")
    if "test_key_prefix" not in cols:
        conn.execute("ALTER TABLE partner_accounts ADD COLUMN test_key_prefix TEXT")
    if "access_until" not in cols:
        conn.execute("ALTER TABLE partner_accounts ADD COLUMN access_until TEXT")
    if "access_started_at" not in cols:
        conn.execute("ALTER TABLE partner_accounts ADD COLUMN access_started_at TEXT")
    for col, decl in (
        ("allow_voice", "INTEGER NOT NULL DEFAULT 0"),
        ("allow_sms", "INTEGER NOT NULL DEFAULT 0"),
        ("allow_whatsapp", "INTEGER NOT NULL DEFAULT 0"),
        ("allow_email", "INTEGER NOT NULL DEFAULT 0"),
        ("allowed_ip", "TEXT"),
        ("allowed_prefixes", "TEXT"),
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE partner_accounts ADD COLUMN {col} {decl}")


def _channels_from_flags(allow_voice, allow_sms, allow_whatsapp, allow_email):
    out = []
    if allow_voice:
        out.append("voice")
    if allow_sms:
        out.append("sms")
    if allow_whatsapp:
        out.append("whatsapp")
    if allow_email:
        out.append("email")
    return out


def _flags_from_channels(channels):
    ch = set(channels or [])
    return {
        "allow_voice": 1 if "voice" in ch else 0,
        "allow_sms": 1 if "sms" in ch else 0,
        "allow_whatsapp": 1 if "whatsapp" in ch else 0,
        "allow_email": 1 if "email" in ch else 0,
    }


def _parse_prefixes(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip().lstrip("+") for x in raw if str(x).strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(x).strip().lstrip("+") for x in data if str(x).strip()]
    except Exception:
        pass
    return [p.strip().lstrip("+") for p in text.replace(";", ",").split(",") if p.strip()]


def init_partners():
    with _connect() as conn:
        conn.executescript(_CREATE)
        _ensure_test_key_columns(conn)
    _seed_legacy_keys()
    _backfill_test_keys()
    _backfill_access()
    _backfill_whatsapp_channel()
    _backfill_channel_flags()
    with _connect() as conn:
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_partner_test_hash "
                "ON partner_accounts(test_key_hash)"
            )
        except sqlite3.OperationalError:
            pass


def _backfill_channel_flags():
    """Aligne allow_* sur le JSON channels existant (migration sûre)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, channels, allow_sms, allow_voice, allow_whatsapp, allow_email FROM partner_accounts"
        ).fetchall()
        for row in rows:
            try:
                channels = json.loads(row["channels"] or "[]")
            except Exception:
                channels = []
            if not isinstance(channels, list):
                channels = []
            # Si aucune case n'est encore cochée mais channels non vide → backfill
            any_flag = any(
                int(_row_val(row, k) or 0)
                for k in ("allow_sms", "allow_voice", "allow_whatsapp", "allow_email")
            )
            if any_flag:
                continue
            flags = _flags_from_channels(channels)
            conn.execute(
                """
                UPDATE partner_accounts
                SET allow_voice = ?, allow_sms = ?, allow_whatsapp = ?, allow_email = ?
                WHERE id = ?
                """,
                (
                    flags["allow_voice"],
                    flags["allow_sms"],
                    flags["allow_whatsapp"],
                    flags["allow_email"],
                    row["id"],
                ),
            )


def _backfill_test_keys():
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id FROM partner_accounts
            WHERE test_key_hash IS NULL OR test_key_hash = ''
            """
        ).fetchall()
        for row in rows:
            raw = generate_test_key()
            conn.execute(
                """
                UPDATE partner_accounts
                SET test_key_hash = ?, test_key_prefix = ?
                WHERE id = ?
                """,
                (hash_key(raw), _key_prefix(raw), row["id"]),
            )


def _backfill_whatsapp_channel():
    with _connect() as conn:
        rows = conn.execute("SELECT id, channels FROM partner_accounts").fetchall()
        for row in rows:
            try:
                channels = json.loads(row["channels"] or "[]")
            except Exception:
                channels = []
            if not isinstance(channels, list):
                continue
            if "whatsapp" in channels:
                continue
            if "sms" in channels:
                channels.insert(channels.index("sms") + 1, "whatsapp")
            else:
                channels.append("whatsapp")
            conn.execute(
                "UPDATE partner_accounts SET channels = ? WHERE id = ?",
                (json.dumps(channels), row["id"]),
            )


def _backfill_access():
    today = _today()
    default_until = _add_days(today, DEFAULT_GRANT_DAYS)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, access_until FROM partner_accounts"
        ).fetchall()
        for row in rows:
            if _date_only(_row_val(row, "access_until")):
                continue
            started = _date_only(row["created_at"]) or today
            conn.execute(
                """
                UPDATE partner_accounts
                SET access_started_at = ?, access_until = ?
                WHERE id = ?
                """,
                (started, default_until, row["id"]),
            )


def _seed_legacy_keys():
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM partner_accounts").fetchone()[0]
        if count:
            return
        for raw_key, meta in PARTNER_KEYS.items():
            plan = meta.get("plan") or "starter"
            spec = PLANS.get(plan) or PLANS["starter"]
            channels = meta.get("channels") or spec["channels"]
            test_raw = generate_test_key()
            started = _today()
            until = _add_days(started, DEFAULT_GRANT_DAYS)
            conn.execute(
                """
                INSERT INTO partner_accounts
                (name, email, plan, channels, key_hash, key_prefix,
                 test_key_hash, test_key_prefix, status,
                 daily_quota, used_today, used_on, created_at,
                 access_started_at, access_until)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 0, ?, ?, ?, ?)
                """,
                (
                    meta.get("name") or "Partenaire",
                    "",
                    plan,
                    json.dumps(channels),
                    hash_key(raw_key),
                    _key_prefix(raw_key),
                    hash_key(test_raw),
                    _key_prefix(test_raw),
                    spec["daily_quota"],
                    started,
                    _now(),
                    started,
                    until,
                ),
            )


def find_by_api_key(raw_key):
    raw = (raw_key or "").strip()
    if not raw:
        return None
    digest = hash_key(raw)
    prefer_test = raw.startswith("sk_test_")
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM partner_accounts").fetchall()
    for row in rows:
        if prefer_test:
            stored = _row_val(row, "test_key_hash") or ""
            if stored and hmac.compare_digest(stored, digest):
                partner = _row_to_partner(row)
                partner["key_mode"] = "test"
                return partner
            continue
        stored = row["key_hash"] or ""
        if stored and hmac.compare_digest(stored, digest):
            partner = _row_to_partner(row)
            partner["key_mode"] = "live"
            return partner
    return None


def list_accounts(include_email=False):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM partner_accounts ORDER BY id DESC"
        ).fetchall()
    out = []
    for row in rows:
        item = _row_to_partner(row)
        if not include_email:
            item.pop("email", None)
        out.append(item)
    return out


def create_account(
    name,
    email,
    plan,
    days=None,
    allow_voice=_UNSET,
    allow_sms=_UNSET,
    allow_whatsapp=_UNSET,
    allow_email=_UNSET,
    allowed_ip=_UNSET,
    allowed_prefixes=_UNSET,
):
    plan = (plan or "starter").strip().lower()
    if plan not in PLANS:
        return None, "plan_invalide"
    name = (name or "").strip()
    if len(name) < 2 or len(name) > 80:
        return None, "nom_invalide"
    email = (email or "").strip().lower()
    if email and ("@" not in email or len(email) > 120):
        return None, "email_invalide"

    grant_days = _parse_grant_days(days)
    spec = PLANS[plan]
    flags_provided = any(
        value is not _UNSET
        for value in (allow_voice, allow_sms, allow_whatsapp, allow_email)
    )
    flags = _flags_from_channels(spec["channels"])
    if flags_provided:
        if allow_voice is not _UNSET:
            flags["allow_voice"] = 1 if _as_bool(allow_voice) else 0
        if allow_sms is not _UNSET:
            flags["allow_sms"] = 1 if _as_bool(allow_sms) else 0
        if allow_whatsapp is not _UNSET:
            flags["allow_whatsapp"] = 1 if _as_bool(allow_whatsapp) else 0
        if allow_email is not _UNSET:
            flags["allow_email"] = 1 if _as_bool(allow_email) else 0
        channels = _channels_from_flags(
            flags["allow_voice"],
            flags["allow_sms"],
            flags["allow_whatsapp"],
            flags["allow_email"],
        )
    else:
        channels = list(spec["channels"])
    ip_value = None if allowed_ip is _UNSET else ((allowed_ip or "").strip() or None)
    prefix_value = (
        None
        if allowed_prefixes is _UNSET
        else json.dumps(_parse_prefixes(allowed_prefixes) or [])
    )
    raw_key = generate_api_key()
    test_raw = generate_test_key()
    started = _today()
    until = _add_days(started, grant_days)
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO partner_accounts
            (name, email, plan, channels, key_hash, key_prefix,
             test_key_hash, test_key_prefix, status,
             daily_quota, used_today, used_on, created_at,
             access_started_at, access_until,
             allow_voice, allow_sms, allow_whatsapp, allow_email,
             allowed_ip, allowed_prefixes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 0, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                email,
                plan,
                json.dumps(channels),
                hash_key(raw_key),
                _key_prefix(raw_key),
                hash_key(test_raw),
                _key_prefix(test_raw),
                spec["daily_quota"],
                started,
                _now(),
                started,
                until,
                flags["allow_voice"],
                flags["allow_sms"],
                flags["allow_whatsapp"],
                flags["allow_email"],
                ip_value,
                prefix_value,
            ),
        )
        account_id = cur.lastrowid
    partner = get_account(account_id)
    return {"account": partner, "api_key": raw_key, "test_api_key": test_raw}, None


def get_account(account_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM partner_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
    return _row_to_partner(row)


def revoke_account(account_id):
    if not get_account(account_id):
        return False
    with _connect() as conn:
        conn.execute(
            "UPDATE partner_accounts SET status = 'revoked' WHERE id = ?",
            (account_id,),
        )
    return True


def delete_account(account_id):
    partner = get_account(account_id)
    if not partner:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM partner_accounts WHERE id = ?", (account_id,))
    return True


def activate_account(account_id):
    if not get_account(account_id):
        return False
    with _connect() as conn:
        conn.execute(
            "UPDATE partner_accounts SET status = 'active' WHERE id = ?",
            (account_id,),
        )
    return True


def renew_access(account_id, days=None):
    grant_days = _parse_grant_days(days)
    partner = get_account(account_id)
    if not partner:
        return None, "compte_introuvable"
    today = _today()
    current = partner.get("access_until") or today
    left = _days_left(current)
    start = today if left < 0 else current
    until = _add_days(start, grant_days)
    with _connect() as conn:
        conn.execute(
            """
            UPDATE partner_accounts
            SET access_started_at = ?, access_until = ?, status = 'active'
            WHERE id = ?
            """,
            (today, until, account_id),
        )
    return get_account(account_id), None


def update_account(
    account_id,
    name=None,
    email=None,
    plan=None,
    allow_voice=_UNSET,
    allow_sms=_UNSET,
    allow_whatsapp=_UNSET,
    allow_email=_UNSET,
    allowed_ip=_UNSET,
    allowed_prefixes=_UNSET,
):
    partner = get_account(account_id)
    if not partner:
        return None, "compte_introuvable"

    next_name = partner["name"] if name is None else (name or "").strip()
    if len(next_name) < 2 or len(next_name) > 80:
        return None, "nom_invalide"

    next_email = partner.get("email") or "" if email is None else (email or "").strip().lower()
    if next_email and ("@" not in next_email or len(next_email) > 120):
        return None, "email_invalide"

    next_plan = partner["plan"] if plan is None else (plan or "").strip().lower()
    if next_plan not in PLANS:
        return None, "plan_invalide"

    spec = PLANS[next_plan]
    flags_provided = any(
        value is not _UNSET
        for value in (allow_voice, allow_sms, allow_whatsapp, allow_email)
    )
    plan_changed = next_plan != partner["plan"]
    if flags_provided:
        next_allow_voice = (
            partner.get("allow_voice") if allow_voice is _UNSET else _as_bool(allow_voice)
        )
        next_allow_sms = partner.get("allow_sms") if allow_sms is _UNSET else _as_bool(allow_sms)
        next_allow_whatsapp = (
            partner.get("allow_whatsapp") if allow_whatsapp is _UNSET else _as_bool(allow_whatsapp)
        )
        next_allow_email = (
            partner.get("allow_email") if allow_email is _UNSET else _as_bool(allow_email)
        )
        next_channels = _channels_from_flags(
            next_allow_voice, next_allow_sms, next_allow_whatsapp, next_allow_email
        )
    elif plan_changed:
        next_channels = list(spec["channels"])
        flags = _flags_from_channels(next_channels)
        next_allow_voice = bool(flags["allow_voice"])
        next_allow_sms = bool(flags["allow_sms"])
        next_allow_whatsapp = bool(flags["allow_whatsapp"])
        next_allow_email = bool(flags["allow_email"])
    else:
        next_channels = list(partner.get("channels") or spec["channels"])
        next_allow_voice = bool(partner.get("allow_voice"))
        next_allow_sms = bool(partner.get("allow_sms"))
        next_allow_whatsapp = bool(partner.get("allow_whatsapp"))
        next_allow_email = bool(partner.get("allow_email"))

    next_ip = partner.get("allowed_ip") if allowed_ip is _UNSET else ((allowed_ip or "").strip() or None)
    if allowed_prefixes is _UNSET:
        next_prefixes = json.dumps(partner.get("allowed_prefixes") or [])
    else:
        next_prefixes = json.dumps(_parse_prefixes(allowed_prefixes) or [])

    with _connect() as conn:
        conn.execute(
            """
            UPDATE partner_accounts
            SET name = ?, email = ?, plan = ?, channels = ?, daily_quota = ?,
                allow_voice = ?, allow_sms = ?, allow_whatsapp = ?, allow_email = ?,
                allowed_ip = ?, allowed_prefixes = ?
            WHERE id = ?
            """,
            (
                next_name,
                next_email,
                next_plan,
                json.dumps(next_channels),
                spec["daily_quota"],
                1 if next_allow_voice else 0,
                1 if next_allow_sms else 0,
                1 if next_allow_whatsapp else 0,
                1 if next_allow_email else 0,
                next_ip,
                next_prefixes,
                account_id,
            ),
        )
    return get_account(account_id), None


def rotate_key(account_id):
    partner = get_account(account_id)
    if not partner:
        return None, "compte_introuvable"
    if partner.get("status") != "active":
        return None, "compte_revoque"
    raw_key = generate_api_key()
    test_raw = generate_test_key()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE partner_accounts
            SET key_hash = ?, key_prefix = ?,
                test_key_hash = ?, test_key_prefix = ?
            WHERE id = ?
            """,
            (
                hash_key(raw_key),
                _key_prefix(raw_key),
                hash_key(test_raw),
                _key_prefix(test_raw),
                account_id,
            ),
        )
    updated = get_account(account_id)
    return {"account": updated, "api_key": raw_key, "test_api_key": test_raw}, None


def ensure_test_key(account_id):
    partner = get_account(account_id)
    if not partner:
        return None, "compte_introuvable"
    with _connect() as conn:
        row = conn.execute(
            "SELECT test_key_hash FROM partner_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        existing = (row["test_key_hash"] if row else None) or ""
        if existing:
            return {
                "account": partner,
                "test_api_key": None,
                "created": False,
                "test_key_prefix": partner.get("test_key_prefix") or "",
            }, None
        raw = generate_test_key()
        conn.execute(
            """
            UPDATE partner_accounts
            SET test_key_hash = ?, test_key_prefix = ?
            WHERE id = ?
            """,
            (hash_key(raw), _key_prefix(raw), account_id),
        )
    return {
        "account": get_account(account_id),
        "test_api_key": raw,
        "created": True,
    }, None


def rotate_test_key(account_id):
    partner = get_account(account_id)
    if not partner:
        return None, "compte_introuvable"
    if partner.get("status") != "active":
        return None, "compte_revoque"
    raw = generate_test_key()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE partner_accounts
            SET test_key_hash = ?, test_key_prefix = ?
            WHERE id = ?
            """,
            (hash_key(raw), _key_prefix(raw), account_id),
        )
    return {"account": get_account(account_id), "test_api_key": raw}, None


def quota_ok(partner):
    if not partner:
        return False
    return int(partner.get("used_today") or 0) < int(partner.get("daily_quota") or 0)


def consume_quota(account_id):
    today = _today()
    with _connect() as conn:
        row = conn.execute(
            "SELECT used_today, used_on, daily_quota FROM partner_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if not row:
            return False
        used = int(row["used_today"] or 0)
        if row["used_on"] != today:
            used = 0
        if used >= int(row["daily_quota"]):
            return False
        conn.execute(
            """
            UPDATE partner_accounts
            SET used_today = ?, used_on = ?, last_used_at = ?
            WHERE id = ?
            """,
            (used + 1, today, _now(), account_id),
        )
    return True


def touch_last_used(account_id):
    with _connect() as conn:
        conn.execute(
            "UPDATE partner_accounts SET last_used_at = ? WHERE id = ?",
            (_now(), account_id),
        )


_PLAN_CHART = {
    "starter": {"label": "Starter", "color": "#b8a48a"},
    "pro": {"label": "Pro", "color": "#c17b6a"},
    "business": {"label": "Business", "color": "#6d8b7b"},
}

_CHANNEL_CHART = {
    "voice": {"label": "Voix", "color": "#c17b6a"},
    "sms": {"label": "SMS", "color": "#6d8b7b"},
    "whatsapp": {"label": "WhatsApp", "color": "#5f9e6e"},
    "email": {"label": "E-mail", "color": "#b8a48a"},
}


def _created_day(iso):
    if not iso:
        return None
    return str(iso)[:10]


def partner_balances():
    accounts = list_accounts(include_email=True)
    items = []
    remaining_sum = 0
    cap_sum = 0
    used_sum = 0
    low = 0
    empty = 0
    for item in accounts:
        row = {
            "id": item["id"],
            "name": item["name"],
            "email": item.get("email") or "",
            "plan": item.get("plan") or "starter",
            "status": item.get("status") or "active",
            "channels": item.get("channels") or [],
            "daily_quota": int(item.get("daily_quota") or 0),
            "used_today": int(item.get("used_today") or 0),
            "remaining_today": int(item.get("remaining_today") or 0),
            "remaining_pct": float(item.get("remaining_pct") or 0),
            "quota_used_pct": float(item.get("quota_used_pct") or 0),
            "quota_state": item.get("quota_state") or "ok",
            "access_until": item.get("access_until") or "",
            "days_left": int(item.get("days_left") if item.get("days_left") is not None else -1),
            "access_state": item.get("access_state") or "ok",
        }
        items.append(row)
        if row["status"] == "active":
            remaining_sum += row["remaining_today"]
            cap_sum += row["daily_quota"]
            used_sum += row["used_today"]
            if row["quota_state"] == "low":
                low += 1
            elif row["quota_state"] == "empty":
                empty += 1
    items.sort(
        key=lambda row: (
            0 if row["access_state"] == "expired" else 1 if row["access_state"] == "expiring" else 2,
            row["days_left"],
            (row["name"] or "").lower(),
        )
    )
    expired = [row for row in items if row["access_state"] == "expired"]
    expiring = [row for row in items if row["access_state"] == "expiring"]
    return {
        "generated_at": _now(),
        "total": len(items),
        "active": sum(1 for row in items if row["status"] == "active"),
        "quota_used_today": used_sum,
        "quota_cap_today": cap_sum,
        "remaining_today": remaining_sum,
        "remaining_pct": round((remaining_sum / cap_sum) * 100, 1) if cap_sum else 0.0,
        "low_count": low,
        "empty_count": empty,
        "expired_count": len(expired),
        "expiring_count": len(expiring),
        "expired": expired,
        "expiring": expiring,
        "accounts": items,
    }


def partner_stats():
    accounts = list_accounts(include_email=False)
    active = [a for a in accounts if a.get("status") == "active"]
    revoked = [a for a in accounts if a.get("status") == "revoked"]
    by_plan = {key: 0 for key in PLANS}
    quota_used = 0
    quota_cap = 0
    channel_counts = {"voice": 0, "sms": 0, "whatsapp": 0, "email": 0}
    quota_usage = []
    today = datetime.now(timezone.utc).date()
    created_map = {
        (today - timedelta(days=offset)).isoformat(): 0
        for offset in range(13, -1, -1)
    }

    for item in accounts:
        plan = item.get("plan") or "starter"
        by_plan[plan] = by_plan.get(plan, 0) + 1
        day = _created_day(item.get("created_at"))
        if day in created_map:
            created_map[day] += 1
        used = int(item.get("used_today") or 0)
        cap = int(item.get("daily_quota") or 0)
        if item.get("status") == "active":
            quota_used += used
            quota_cap += cap
            for channel in item.get("channels") or []:
                if channel in channel_counts:
                    channel_counts[channel] += 1
            quota_usage.append({
                "id": item["id"],
                "name": item["name"],
                "plan": plan,
                "used": used,
                "cap": cap,
                "remaining": int(item.get("remaining_today") or 0),
                "pct": round((used / cap) * 100, 1) if cap else 0,
                "remaining_pct": float(item.get("remaining_pct") or 0),
                "quota_state": item.get("quota_state") or "ok",
            })

    quota_usage.sort(key=lambda row: row["used"], reverse=True)

    return {
        "total": len(accounts),
        "active": len(active),
        "revoked": len(revoked),
        "by_plan": by_plan,
        "quota_used_today": quota_used,
        "quota_cap_today": quota_cap,
        "remaining_today": max(quota_cap - quota_used, 0),
        "quota_pct": round((quota_used / quota_cap) * 100, 1) if quota_cap else 0,
        "expired_count": sum(1 for a in accounts if a.get("access_state") == "expired"),
        "expiring_count": sum(1 for a in accounts if a.get("access_state") == "expiring"),
        "channels_enabled": channel_counts,
        "plans": PLANS,
        "charts": {
            "plans": [
                {
                    "key": key,
                    "label": _PLAN_CHART.get(key, {}).get("label") or key,
                    "value": by_plan.get(key, 0),
                    "color": _PLAN_CHART.get(key, {}).get("color") or "#b8a48a",
                }
                for key in PLANS
            ],
            "status": [
                {"key": "active", "label": "Actifs", "value": len(active), "color": "#6d8b7b"},
                {"key": "revoked", "label": "Révoqués", "value": len(revoked), "color": "#c17b6a"},
            ],
            "channels": [
                {
                    "key": key,
                    "label": meta["label"],
                    "value": channel_counts.get(key, 0),
                    "color": meta["color"],
                }
                for key, meta in _CHANNEL_CHART.items()
            ],
            "quota_usage": quota_usage[:12],
            "created": [
                {"label": day, "value": count}
                for day, count in created_map.items()
            ],
        },
    }
