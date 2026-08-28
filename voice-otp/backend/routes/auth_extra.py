from flask import Blueprint, request, jsonify

from db import log_event
from otp.deliver import deliver_email, deliver_sms
from otp.generator import generate_otp, store_otp
from otp.security import limiter, OTP_REQUEST_LIMIT

extra_bp = Blueprint("auth_extra", __name__)


def _ip():
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or (request.remote_addr or "")


@extra_bp.route("/auth/request-email-otp", methods=["POST"])
@limiter.limit(OTP_REQUEST_LIMIT)
def request_email_otp():
    data = request.get_json(silent=True) or {}
    user_id = data.get("userId")
    email = data.get("email")

    if not user_id or not email:
        return jsonify({"status": "error", "detail": "userId et email requis"}), 400

    otp = generate_otp()
    ok, err = deliver_email(email, otp)
    if not ok:
        log_event(user_id, "email", email, "failed", _ip())
        return jsonify({"status": "error", "detail": err}), 502

    store_otp(user_id, otp)
    log_event(user_id, "email", email, "sent", _ip())
    print(f"[EMAIL] OTP envoyé à l'utilisateur {user_id}")
    return jsonify({"status": "sent"}), 200


@extra_bp.route("/auth/request-sms-otp", methods=["POST"])
@limiter.limit(OTP_REQUEST_LIMIT)
def request_sms_otp():
    data = request.get_json(silent=True) or {}
    user_id = data.get("userId")
    phone_number = (data.get("phoneNumber") or "").strip()

    if not user_id or not phone_number:
        return jsonify({"status": "error", "detail": "userId et phoneNumber requis"}), 400

    digits = "".join(ch for ch in phone_number if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return jsonify({"status": "error", "detail": "Numéro de téléphone invalide"}), 400

    otp = generate_otp()
    ok, err = deliver_sms(digits, otp)
    if not ok:
        log_event(user_id, "sms", digits, "failed", _ip())
        return jsonify({"status": "error", "detail": str(err)[:400]}), 502

    store_otp(user_id, otp)
    log_event(user_id, "sms", digits, "sent", _ip())
    print(f"[SMS] OTP envoyé à l'utilisateur {user_id}")
    return jsonify({"status": "sent", "demo": False}), 200
