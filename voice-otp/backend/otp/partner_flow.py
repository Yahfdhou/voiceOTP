from db import last_request_context, log_event
from otp.deliver import deliver_email, deliver_sms, deliver_voice, deliver_whatsapp, verify_whatsapp_code
from otp.generator import (
    OTP_TTL,
    delete_otp,
    generate_otp,
    peek_whatsapp_phone,
    store_otp,
    store_whatsapp_pending,
    verify_otp,
)
from otp.security import (
    MAX_VERIFY_ATTEMPTS,
    record_failed_attempt,
    reset_attempts,
    too_many_attempts,
)
from partners import (
    channel_enabled,
    consume_quota,
    destination_country_ok,
    destination_prefixes_for,
    quota_ok,
    touch_last_used,
)
from product_config import VOICE_LOCAL_EXT, voice_is_telnyx_cloud, voice_is_trunk


def normalize_phone(value):
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def _is_test(partner):
    return (partner or {}).get("key_mode") == "test"


def _scope(partner):
    """Isole les OTP Redis par partenaire (anti cross-tenant)."""
    return (partner or {}).get("id")


def _write_log(partner, user_id, channel, dest, status, source_ip):
    log_event(
        user_id,
        channel,
        dest,
        status,
        source_ip,
        (partner or {}).get("id"),
        is_test=_is_test(partner),
    )


def _maybe_consume(partner):
    if not partner:
        return
    if _is_test(partner):
        touch_last_used(partner["id"])
        return
    consume_quota(partner["id"])


def _country_error(partner, dest, channel, source_ip):
    _write_log(partner, "-", channel, dest, "invalid_destination_country", source_ip)
    return {
        "error": "invalid_destination_country",
        "status": "error",
        "detail": "invalid_destination_country",
        "destination": dest,
        "allowed_prefixes": destination_prefixes_for(partner),
    }, 400


def send_otp(partner, channel, data, source_ip):
    if not channel_enabled(partner, channel):
        return {
            "error": "channel_disabled_for_account",
            "status": "error",
            "detail": "channel_disabled_for_account",
            "channel": channel,
            "plan": (partner or {}).get("plan"),
        }, 403

    if not _is_test(partner) and not quota_ok(partner):
        return {
            "status": "error",
            "detail": "quota_exceeded",
            "plan": partner.get("plan"),
            "daily_quota": partner.get("daily_quota"),
        }, 429

    user_id = (data.get("userId") or "").strip()
    if channel == "voice":
        if not user_id:
            return {"status": "error", "detail": "userId requis"}, 400
        voice_mode = (
            data.get("voiceMode")
            or data.get("voice_mode")
            or ""
        ).strip().lower()
        use_lab = voice_mode in ("lab", "linphone", "local", "1000")
        if use_lab and not _is_test(partner):
            return {
                "status": "error",
                "detail": "voice_lab_test_only",
                "hint": "Le mode Linphone (lab) est réservé aux clés sk_test_.",
            }, 403
        if use_lab:
            dest = VOICE_LOCAL_EXT
            deliver_mode = "lab"
        elif voice_is_trunk() or voice_is_telnyx_cloud() or voice_mode in (
            "live", "telnyx", "real", "cloud", "trunk", "sip"
        ):
            phone = (data.get("phoneNumber") or "").strip()
            if not phone:
                return {"status": "error", "detail": "userId et phoneNumber requis"}, 400
            dest = normalize_phone(phone)
            if not dest:
                return {"status": "error", "detail": "Numéro de téléphone invalide"}, 400
            if not destination_country_ok(dest, partner):
                return _country_error(partner, dest, "voice", source_ip)
            if voice_mode in ("trunk", "sip"):
                deliver_mode = "trunk"
            elif voice_mode in ("live", "telnyx", "real", "cloud") or voice_is_telnyx_cloud():
                deliver_mode = "live"
            else:
                deliver_mode = "trunk"
        else:
            dest = VOICE_LOCAL_EXT
            deliver_mode = "lab"
        otp = generate_otp()
        store_otp(user_id, otp, scope=_scope(partner))
        ok, result = deliver_voice(otp, dest, mode=deliver_mode)
        if not ok:
            _write_log(partner, user_id, "voice", dest, "failed", source_ip)
            return {"status": "error", "detail": str(result), "channel": "voice"}, 502
        _write_log(partner, user_id, "voice", dest, "sent", source_ip)
        _maybe_consume(partner)
        payload = _sent_payload("voice", partner)
        payload["voiceMode"] = "lab" if use_lab else "live"
        return payload, 200

    if channel == "sms":
        phone = (data.get("phoneNumber") or "").strip()
        if not user_id or not phone:
            return {"status": "error", "detail": "userId et phoneNumber requis"}, 400
        digits = normalize_phone(phone)
        if not digits:
            return {"status": "error", "detail": "Numéro de téléphone invalide"}, 400
        if not destination_country_ok(digits, partner):
            return _country_error(partner, digits, "sms", source_ip)
        otp = generate_otp()
        ok, err = deliver_sms(digits, otp)
        if not ok:
            _write_log(partner, user_id, "sms", digits, "failed", source_ip)
            return {"status": "error", "detail": str(err)[:400], "channel": "sms"}, 502
        store_otp(user_id, otp, scope=_scope(partner))
        _write_log(partner, user_id, "sms", digits, "sent", source_ip)
        _maybe_consume(partner)
        return _sent_payload("sms", partner), 200

    if channel == "whatsapp":
        phone = (data.get("phoneNumber") or "").strip()
        if not user_id or not phone:
            return {"status": "error", "detail": "userId et phoneNumber requis"}, 400
        digits = normalize_phone(phone)
        if not digits:
            return {"status": "error", "detail": "Numéro de téléphone invalide"}, 400
        if not destination_country_ok(digits, partner):
            return _country_error(partner, digits, "whatsapp", source_ip)
        ok, err = deliver_whatsapp(digits)
        if not ok:
            _write_log(partner, user_id, "whatsapp", digits, "failed", source_ip)
            return {"status": "error", "detail": str(err)[:400], "channel": "whatsapp"}, 502
        store_whatsapp_pending(user_id, digits, scope=_scope(partner))
        _write_log(partner, user_id, "whatsapp", digits, "sent", source_ip)
        _maybe_consume(partner)
        return _sent_payload("whatsapp", partner), 200

    if channel == "email":
        email = (data.get("email") or "").strip()
        if not user_id or not email:
            return {"status": "error", "detail": "userId et email requis"}, 400
        otp = generate_otp()
        ok, err = deliver_email(email, otp)
        if not ok:
            _write_log(partner, user_id, "email", email, "failed", source_ip)
            return {"status": "error", "detail": str(err)[:400], "channel": "email"}, 502
        store_otp(user_id, otp, scope=_scope(partner))
        _write_log(partner, user_id, "email", email, "sent", source_ip)
        _maybe_consume(partner)
        return _sent_payload("email", partner), 200

    return {"status": "error", "detail": "channel_inconnu"}, 400


def _sent_payload(channel, partner):
    payload = {
        "status": "sent",
        "channel": channel,
        "expiresIn": OTP_TTL,
    }
    if _is_test(partner):
        payload["mode"] = "test"
    return payload


def verify_for_partner(partner, data, source_ip):
    user_id = (data.get("userId") or "").strip()
    otp_input = data.get("otp")
    if not user_id or not otp_input:
        return {"ok": False, "reason": "missing"}, 400

    scope = _scope(partner)
    ctx = last_request_context(
        user_id,
        partner_id=(partner or {}).get("id"),
        is_test=_is_test(partner),
    )

    if too_many_attempts(user_id, scope=scope):
        _write_log(
            partner, user_id, ctx["channel"], ctx["destination"], "too_many_attempts", source_ip
        )
        return _reject_too_many(user_id, scope=scope)

    wa_phone = peek_whatsapp_phone(user_id, scope=scope)
    if wa_phone:
        ok, reason = verify_whatsapp_code(wa_phone, otp_input)
        if ok:
            reset_attempts(user_id, scope=scope)
            delete_otp(user_id, scope=scope)
            _write_log(partner, user_id, "whatsapp", wa_phone, "verified", source_ip)
            payload = {"ok": True, "channel": "whatsapp"}
            if _is_test(partner):
                payload["mode"] = "test"
            return payload, 200
        if reason not in ("invalid", "expired", "locked"):
            _write_log(partner, user_id, "whatsapp", wa_phone, "failed", source_ip)
            return {"status": "error", "detail": str(reason)[:400], "channel": "whatsapp"}, 502
        if reason == "invalid":
            count = record_failed_attempt(user_id, scope=scope)
            if count >= MAX_VERIFY_ATTEMPTS:
                _write_log(
                    partner, user_id, "whatsapp", wa_phone, "too_many_attempts", source_ip
                )
                return _reject_too_many(user_id, scope=scope)
            _write_log(partner, user_id, "whatsapp", wa_phone, "invalid", source_ip)
            return {"ok": False, "reason": "invalid"}, 400
        if reason == "expired":
            _write_log(partner, user_id, "whatsapp", wa_phone, "expired", source_ip)
        return {"ok": False, "reason": reason}, 400

    ok, reason = verify_otp(user_id, otp_input, scope=scope)
    if ok:
        reset_attempts(user_id, scope=scope)
        _write_log(partner, user_id, ctx["channel"], ctx["destination"], "verified", source_ip)
        payload = {"ok": True, "channel": ctx["channel"]}
        if _is_test(partner):
            payload["mode"] = "test"
        return payload, 200

    if reason == "invalid":
        count = record_failed_attempt(user_id, scope=scope)
        if count >= MAX_VERIFY_ATTEMPTS:
            _write_log(
                partner, user_id, ctx["channel"], ctx["destination"], "too_many_attempts", source_ip
            )
            return _reject_too_many(user_id, scope=scope)
        _write_log(partner, user_id, ctx["channel"], ctx["destination"], "invalid", source_ip)
        return {"ok": False, "reason": "invalid"}, 400

    if reason == "locked":
        _write_log(
            partner, user_id, ctx["channel"], ctx["destination"], "too_many_attempts", source_ip
        )
        return _reject_too_many(user_id, scope=scope)

    if reason == "expired":
        _write_log(partner, user_id, ctx["channel"], ctx["destination"], "expired", source_ip)
    return {"ok": False, "reason": reason}, 400


def _reject_too_many(user_id, scope=None):
    delete_otp(user_id, scope=scope)
    return {"ok": False, "reason": "too_many_attempts"}, 429
