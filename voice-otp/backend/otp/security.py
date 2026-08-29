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
VERIFY_REQUEST_LIMIT = "60 per minute"
# Dashboard Nuxt poll (Live Traffic 5s + stats) — large assez pour l’UI,
# toujours limitant pour brute-force massif de X-Admin-Key.
ADMIN_REQUEST_LIMIT = "600 per minute"


def otp_send_limit():
    raw = (request.headers.get("X-Api-Key") or "").strip()
    if raw.startswith("sk_test_"):
        return OTP_TEST_REQUEST_LIMIT
    return OTP_REQUEST_LIMIT


_attempt_fallback = {}


def trust_proxy():
    return os.getenv("TRUST_PROXY", "1").strip().lower() not in ("0", "false", "no")


def client_ip():
    """IP client. X-Forwarded-For seulement si TRUST_PROXY=1 (derrière Nginx)."""
    if trust_proxy():
        forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if forwarded:
            return forwarded
        real_ip = (request.headers.get("X-Real-IP") or "").strip()
        if real_ip:
            return real_ip
    return request.remote_addr or ""


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
    return "ip:" + (client_ip() or get_remote_address() or "unknown")


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


def _scope_token(scope=None):
    if scope is None or scope == "":
        return "g"
    return f"p{scope}"


def _attempt_key(user_id, scope=None):
    return f"attempts:{_scope_token(scope)}:{user_id}"


def get_attempts(user_id, scope=None):
    key = _attempt_key(user_id, scope)
    client = _redis()
    if client is not None:
        raw = client.get(key)
        return int(raw) if raw else 0
    item = _attempt_fallback.get(key)
    if not item:
        return 0
    count, expires_at = item
    if expires_at <= time.time():
        _attempt_fallback.pop(key, None)
        return 0
    return int(count)


def too_many_attempts(user_id, scope=None):
    return get_attempts(user_id, scope=scope) >= MAX_VERIFY_ATTEMPTS


def record_failed_attempt(user_id, ttl=OTP_TTL, scope=None):
    count = get_attempts(user_id, scope=scope) + 1
    key = _attempt_key(user_id, scope)
    client = _redis()
    if client is not None:
        client.setex(key, ttl, count)
    else:
        _attempt_fallback[key] = (count, time.time() + ttl)
    return count


def reset_attempts(user_id, scope=None):
    key = _attempt_key(user_id, scope)
    client = _redis()
    if client is not None:
        client.delete(key)
    _attempt_fallback.pop(key, None)


def reject_too_many_attempts(user_id, scope=None):
    from otp.generator import delete_otp

    delete_otp(user_id, scope=scope)
    return jsonify({"ok": False, "reason": "too_many_attempts"}), 429
