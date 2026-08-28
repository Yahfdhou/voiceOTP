import hashlib
import hmac
import os
import secrets
import time

import env_load  # noqa: F401

try:
    import redis
except Exception:
    redis = None

OTP_TTL = 180
MAX_ATTEMPTS = 5
OTP_SECRET = os.getenv("OTP_SECRET", "").strip() or "voice-otp-dev-change-me"

_fallback_store = {}


def _redis():
    if redis is None:
        return None
    try:
        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        client.ping()
        return client
    except Exception:
        return None


def generate_otp(length=6):
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _digest(user_id, otp):
    return hmac.new(
        OTP_SECRET.encode(),
        f"{user_id}:{otp}".encode(),
        hashlib.sha256,
    ).hexdigest()


def store_otp(user_id, otp, ttl=OTP_TTL):
    payload = f"{_digest(user_id, otp)}|{0}|{time.time() + ttl}"
    client = _redis()
    if client is not None:
        client.setex(f"otp:{user_id}", ttl, payload)
    else:
        _fallback_store[user_id] = payload
    from otp.security import reset_attempts
    reset_attempts(user_id)


def store_whatsapp_pending(user_id, phone, ttl=OTP_TTL):
    """Session WhatsApp : le code reste chez ChinqIT, on ne stocke que le numéro."""
    payload = f"wa|{phone}|{time.time() + ttl}"
    client = _redis()
    if client is not None:
        client.setex(f"otp:{user_id}", ttl, payload)
    else:
        _fallback_store[user_id] = payload
    from otp.security import reset_attempts
    reset_attempts(user_id)


def peek_whatsapp_phone(user_id):
    raw = _load(user_id)
    if not raw or not raw.startswith("wa|"):
        return None
    parts = raw.split("|", 2)
    if len(parts) < 3:
        return None
    phone, expires_s = parts[1], parts[2]
    try:
        if float(expires_s) <= time.time():
            return None
    except (TypeError, ValueError):
        return None
    return phone or None


def delete_otp(user_id):
    _save(user_id, "", 0)


def _load(user_id):
    client = _redis()
    if client is not None:
        raw = client.get(f"otp:{user_id}")
        return raw.decode() if raw else None
    return _fallback_store.get(user_id)


def _save(user_id, payload, ttl):
    client = _redis()
    if client is not None:
        if ttl <= 0:
            client.delete(f"otp:{user_id}")
            return
        client.setex(f"otp:{user_id}", ttl, payload)
        return
    if ttl <= 0:
        _fallback_store.pop(user_id, None)
        return
    _fallback_store[user_id] = payload


def active_otp_count():
    client = _redis()
    if client is not None:
        return len(client.keys("otp:*"))
    now = time.time()
    n = 0
    for raw in _fallback_store.values():
        try:
            _digest_s, _attempts, expires_s = raw.split("|", 2)
            if float(expires_s) > now:
                n += 1
        except Exception:
            n += 1
    return n


def redis_tool_status():
    client = _redis()
    if client is None:
        count = active_otp_count()
        return {
            "connected": False,
            "total_keys": count,
            "oldest_key_age_seconds": None,
        }
    keys = client.keys("otp:*")
    ttls = [client.ttl(k) for k in keys]
    remaining = [int(t) for t in ttls if t is not None and t >= 0]
    return {
        "connected": True,
        "total_keys": len(keys),
        "oldest_key_age_seconds": min(remaining) if remaining else None,
    }


def flush_otp_keys():
    client = _redis()
    if client is not None:
        keys = client.keys("otp:*")
        if not keys:
            return 0
        return int(client.delete(*keys))
    n = len(_fallback_store)
    _fallback_store.clear()
    return n


def verify_otp(user_id, otp_input):
    raw = _load(user_id)
    if not raw:
        return False, "expired"
    if raw.startswith("wa|"):
        return False, "expired"

    try:
        digest, attempts_s, expires_s = raw.split("|", 2)
        attempts = int(attempts_s)
        expires_at = float(expires_s)
    except ValueError:
        return False, "expired"

    ttl_left = int(expires_at - time.time())
    if ttl_left <= 0:
        _save(user_id, raw, 0)
        return False, "expired"

    if attempts >= MAX_ATTEMPTS:
        _save(user_id, raw, 0)
        return False, "locked"

    candidate = (otp_input or "").strip()
    if hmac.compare_digest(digest, _digest(user_id, candidate)):
        _save(user_id, raw, 0)
        return True, "ok"

    attempts += 1
    _save(user_id, f"{digest}|{attempts}|{expires_at}", ttl_left)
    if attempts >= MAX_ATTEMPTS:
        _save(user_id, raw, 0)
        return False, "locked"
    return False, "invalid"
