import smtplib
from email.message import EmailMessage

import requests

from otp.tts import generate_otp_wav, speak_locally
from channels.telnyx_voice import deliver_telnyx_voice
from pbx.client import trigger_call, trigger_trunk_call
from product_config import voice_is_telnyx_cloud, voice_is_trunk
from sms_config import (
    CHINQIT_API_KEY,
    CHINQIT_API_URL,
    CHINQIT_CHECK_URL,
    CHINQIT_CODE_URL,
)
from smtp_config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM


def deliver_email(email, otp):
    sender = (SMTP_FROM or SMTP_USER or "").strip()
    password = (SMTP_PASS or "").replace(" ", "").strip()
    user = (SMTP_USER or "").strip()
    if not user or not password:
        return False, (
            "SMTP_PASS est vide. Ajoute SMTP_USER et SMTP_PASS dans backend/.env "
            "(mot de passe d'application Gmail, 16 caractères). "
            "https://myaccount.google.com/apppasswords — puis redémarre le serveur."
        )

    msg = EmailMessage()
    msg["Subject"] = "Votre code de vérification"
    msg["From"] = sender
    msg["To"] = email
    msg.set_content(
        f"Bonjour, votre code de vérification est : {otp}. Il expire dans 3 minutes."
    )
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail a refusé le mot de passe. Utilise un mot de passe d'application "
            "(16 lettres), pas le mot de passe Gmail. "
            "https://myaccount.google.com/apppasswords"
        )
    except Exception as e:
        return False, str(e)


def _chinqit_phone(phone_number):
    digits = "".join(ch for ch in (phone_number or "") if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return None
    if digits.startswith("222"):
        return f"+{digits}"
    if len(digits) == 8 and digits[0] in "234":
        return f"+222{digits}"
    return f"+{digits}"


def _chinqit_key():
    api_key = (CHINQIT_API_KEY or "").strip()
    if api_key:
        return api_key, None
    return None, (
        "CHINQIT_API_KEY manquante. Ajoute-la dans backend/.env "
        "(clé depuis https://dashboard.sms.chinqit.com)."
    )


def _chinqit_post(url, payload, label):
    api_key, err = _chinqit_key()
    if err:
        return False, err, {}
    try:
        resp = requests.post(
            url,
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=20,
        )
        try:
            body_json = resp.json()
        except Exception:
            body_json = {}
        raw = (resp.text or "").strip()
        print(f"[{label}] ChinqIT HTTP {resp.status_code} {raw[:200]}")
        if resp.status_code == 200 and body_json.get("success") is True:
            return True, None, body_json
        msg = body_json.get("message")
        err_obj = body_json.get("error")
        err_msg = err_obj.get("message") if isinstance(err_obj, dict) else None
        code = body_json.get("code")
        parts = []
        if isinstance(msg, str) and msg.strip():
            parts.append(msg.strip())
        elif isinstance(err_msg, str) and err_msg.strip():
            parts.append(err_msg.strip())
        if isinstance(code, str) and code.strip():
            parts.append(code.strip())
        if not parts and raw:
            parts.append(raw[:300])
        if not parts:
            parts.append(f"Erreur ChinqIT HTTP {resp.status_code}")
        detail = " — ".join(parts)
        print(f"[{label}] ChinqIT erreur: {detail}")
        return False, detail[:400], body_json
    except Exception as e:
        return False, str(e), {}


def deliver_sms(phone_number, otp):
    to = _chinqit_phone(phone_number)
    if not to:
        return False, "Numéro de téléphone invalide"
    ok, err, _ = _chinqit_post(
        CHINQIT_API_URL,
        {
            "phoneNumber": to,
            "message": f"Votre code de vérification est {otp}",
        },
        "SMS",
    )
    return ok, err


def deliver_whatsapp(phone_number):
    """OTP WhatsApp via ChinqIT POST /api/v2/code (le code est généré chez ChinqIT)."""
    to = _chinqit_phone(phone_number)
    if not to:
        return False, "Numéro de téléphone invalide"
    ok, err, _ = _chinqit_post(
        CHINQIT_CODE_URL,
        {
            "phoneNumber": to,
            "channel": "whatsapp",
            "language": "fr",
        },
        "WhatsApp",
    )
    return ok, err


def verify_whatsapp_code(phone_number, otp_input):
    to = _chinqit_phone(phone_number)
    if not to:
        return False, "expired"
    ok, err, payload = _chinqit_post(
        CHINQIT_CHECK_URL,
        {
            "phoneNumber": to,
            "otp": str(otp_input or "").strip(),
            "channel": "whatsapp",
        },
        "WhatsApp-check",
    )
    if ok or payload.get("verified") is True:
        return True, "ok"
    message = (err or payload.get("message") or "").lower()
    if payload.get("retriesLeft") is not None or "invalid otp" in message:
        return False, "invalid"
    if "expire" in message:
        return False, "expired"
    if err:
        return False, err
    return False, "invalid"


def _deliver_lab_voice(otp, dest="1000"):
    try:
        generate_otp_wav(otp)
    except Exception as e:
        print(f"[TTS] {e}")
    speak_locally(otp)
    return trigger_call(dest or "1000", otp)


def deliver_voice(otp, dest="1000", mode=None):
    """mode lab/linphone → Linphone ; live/telnyx → cloud ; sinon VOICE_PROVIDER."""
    chosen = (mode or "").strip().lower()
    if chosen in ("lab", "linphone", "local", "1000"):
        return _deliver_lab_voice(otp, dest)
    if chosen in ("live", "telnyx", "real", "cloud"):
        return deliver_telnyx_voice(otp, dest)
    if chosen in ("trunk", "sip"):
        return trigger_trunk_call(dest, otp)
    if voice_is_telnyx_cloud():
        return deliver_telnyx_voice(otp, dest)
    if voice_is_trunk():
        return trigger_trunk_call(dest, otp)
    return _deliver_lab_voice(otp, dest)
