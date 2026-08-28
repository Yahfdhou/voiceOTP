import hashlib
import os
import time

from flask import jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

OTP_TTL = 180
MAX_VERIFY_ATTEMPTS = 3
OTP_REQUEST_LIMIT = "20 per 5 minutes"
OTP_TEST_REQUEST_LIMIT = "10 per 5 minutes"


def otp_send_limit():
    raw = (request.headers.get("X-Api-Key") or "").strip()
    if raw.startswith("sk_test_"):
        return OTP_TEST_REQUEST_LIMIT
    return OTP_REQUEST_LIMIT

_attempt_fallback = {}


def _redis():
    try:
        import redis
    except Exception:
        return None
    try:
        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        client.ping()
        return client
    except Exception:
        return None


def _limiter_storage():
    client = _redis()
    if client is not None:
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return "memory://"


def _rate_limit_response(_request_limit=None):
    resp = jsonify({
        "status": "error",
        "detail": "Trop de tentatives, réessayez plus tard",
    })
    resp.status_code = 429
    return resp


def _limit_key():
    raw = (request.headers.get("X-Api-Key") or "").strip()
    if raw:
        return "ak:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
    return get_remote_address()


limiter = Limiter(
    key_func=_limit_key,
    default_limits=[],
    storage_uri=_limiter_storage(),
    in_memory_fallback_enabled=True,
    on_breach=_rate_limit_response,
)


@limiter.request_filter
def _skip_cors_preflight():
    return request.method == "OPTIONS"


def _attempt_key(user_id):
    return f"attempts:{user_id}"


def get_attempts(user_id):
    client = _redis()
    if client is not None:
        raw = client.get(_attempt_key(user_id))
        return int(raw) if raw else 0
    item = _attempt_fallback.get(user_id)
    if not item:
        return 0
    count, expires_at = item
    if expires_at <= time.time():
        _attempt_fallback.pop(user_id, None)
        return 0
    return int(count)


def too_many_attempts(user_id):
    return get_attempts(user_id) >= MAX_VERIFY_ATTEMPTS


def record_failed_attempt(user_id, ttl=OTP_TTL):
    count = get_attempts(user_id) + 1
    client = _redis()
    if client is not None:
        client.setex(_attempt_key(user_id), ttl, count)
    else:
        _attempt_fallback[user_id] = (count, time.time() + ttl)
    return count


def reset_attempts(user_id):
    client = _redis()
    if client is not None:
        client.delete(_attempt_key(user_id))
    _attempt_fallback.pop(user_id, None)


def reject_too_many_attempts(user_id):
    from otp.generator import delete_otp

    delete_otp(user_id)
    return jsonify({"ok": False, "reason": "too_many_attempts"}), 429
