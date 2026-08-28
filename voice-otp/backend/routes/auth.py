from flask import Blueprint, request, jsonify

from channels.email import send_email
from channels.phone import mask_destination, public_countries, to_e164, normalize_email
from channels.sms import send_sms
from db import last_request_context, log_event
from otp.deliver import deliver_voice
from otp.generator import OTP_TTL, generate_otp, store_otp, verify_otp
from otp import rate_limit
from otp.security import (
    limiter,
    OTP_REQUEST_LIMIT,
    MAX_VERIFY_ATTEMPTS,
    record_failed_attempt,
    reject_too_many_attempts,
    reset_attempts,
    too_many_attempts,
)

auth_bp = Blueprint("auth", __name__)
VOICE_LOCAL_EXT = "1000"


def _ip():
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or (request.remote_addr or "")


def _json():
    return request.get_json(silent=True) or {}


def _log_verify(user_id, status):
    ctx = last_request_context(user_id)
    log_event(user_id, ctx["channel"], ctx["destination"], status, _ip())


def _error(detail, status=400, **extra):
    payload = {"status": "error", "detail": detail}
    payload.update(extra)
    return jsonify(payload), status


def _resolve_destination(channel, data):
    if channel == "email":
        return normalize_email(data.get("email"))
    return to_e164(data.get("countryCode"), data.get("nationalNumber"))


def _dispatch(channel, dest, otp):
    if channel == "email":
        return send_email(dest, otp)
    return send_sms(dest, otp)


@auth_bp.route("/auth/countries", methods=["GET"])
def countries():
    return jsonify({"countries": public_countries()}), 200


@auth_bp.route("/auth/request-voice-otp", methods=["POST"])
@limiter.limit(OTP_REQUEST_LIMIT)
def request_voice_otp():
    data = _json()
    user_id = (data.get("userId") or "").strip()
    if not user_id:
        return _error("Identifiant requis.")

    otp = generate_otp()
    store_otp(user_id, otp)

    ok, result = deliver_voice(otp, VOICE_LOCAL_EXT)
    if ok:
        log_event(user_id, "voice", VOICE_LOCAL_EXT, "sent", _ip())
        print(f"[VOICE] OTP envoyé à l'utilisateur {user_id}")
        return jsonify({"status": "sent", "channel": "voice"}), 200

    log_event(user_id, "voice", VOICE_LOCAL_EXT, "failed", _ip())
    print("[VOICE] échec de l'appel")
    return _error(str(result), 502)


@auth_bp.route("/auth/request-otp", methods=["POST"])
def request_otp():
    data = _json()
    user_id = (data.get("userId") or "").strip()
    channel = (data.get("channel") or "").strip().lower()

    if not user_id:
        return _error("Identifiant requis.")
    if channel not in ("sms", "email"):
        return _error("Canal invalide. Utilisez sms ou email.")

    dest, err = _resolve_destination(channel, data)
    if err:
        return _error(err)

    allowed, limit_msg = rate_limit.allow(f"{channel}:{dest}")
    if not allowed:
        return _error(limit_msg, 429, to=mask_destination(channel, dest))

    ip_ok, ip_msg = rate_limit.allow(f"ip:{request.remote_addr}", min_interval=8, max_per_window=20)
    if not ip_ok:
        return _error(ip_msg, 429)

    otp = generate_otp()
    ok, result = _dispatch(channel, dest, otp)
    masked = mask_destination(channel, dest)

    if not ok:
        print(f"[{channel.upper()}] échec d'envoi")
        log_event(user_id, channel, dest, "failed", _ip())
        return _error(str(result), 502, channel=channel, to=masked)

    store_otp(user_id, otp)
    log_event(user_id, channel, dest, "sent", _ip())
    print(f"[{channel.upper()}] envoyé")
    return jsonify({
        "status": "sent",
        "channel": channel,
        "to": masked,
        "demo": False,
        "expiresIn": OTP_TTL,
    }), 200


@auth_bp.route("/auth/verify-otp", methods=["POST"])
def verify_otp_route():
    data = _json()
    user_id = (data.get("userId") or "").strip()
    otp_input = data.get("otp")
    if not user_id or not otp_input:
        return jsonify({"ok": False, "reason": "missing"}), 400

    if too_many_attempts(user_id):
        _log_verify(user_id, "too_many_attempts")
        return reject_too_many_attempts(user_id)

    ok, reason = verify_otp(user_id, otp_input)
    if ok:
        reset_attempts(user_id)
        _log_verify(user_id, "verified")
        return jsonify({"ok": True}), 200

    if reason == "invalid":
        count = record_failed_attempt(user_id)
        if count >= MAX_VERIFY_ATTEMPTS:
            _log_verify(user_id, "too_many_attempts")
            return reject_too_many_attempts(user_id)
        _log_verify(user_id, "invalid")
        return jsonify({"ok": False, "reason": reason}), 400

    if reason == "locked":
        _log_verify(user_id, "too_many_attempts")
        return reject_too_many_attempts(user_id)

    if reason == "expired":
        _log_verify(user_id, "expired")
    return jsonify({"ok": False, "reason": reason}), 400
