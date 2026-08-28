import os

import requests


def _cfg():
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    sender = os.getenv("TWILIO_FROM", "")
    debug = os.getenv("DEBUG_OTP")
    try:
        import sms_config as cfg

        sid = sid or getattr(cfg, "TWILIO_ACCOUNT_SID", "")
        token = token or getattr(cfg, "TWILIO_AUTH_TOKEN", "")
        sender = sender or getattr(cfg, "TWILIO_FROM", "")
        if debug is None:
            debug = getattr(cfg, "DEBUG_OTP", True)
    except Exception:
        if debug is None:
            debug = True
    return {
        "sid": (sid or "").strip(),
        "token": (token or "").strip(),
        "from": (sender or "").strip(),
        "debug": str(debug).lower() in ("1", "true", "yes"),
    }


def send_sms(e164, otp_code):
    cfg = _cfg()
    body = f"Votre code de verification est {otp_code}. Il expire dans 3 minutes."

    if cfg["sid"] and cfg["token"] and cfg["from"]:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['sid']}/Messages.json"
        try:
            resp = requests.post(
                url,
                auth=(cfg["sid"], cfg["token"]),
                data={"To": e164, "From": cfg["from"], "Body": body},
                timeout=20,
            )
            if resp.status_code in (200, 201):
                print(f"[SMS] envoyé à {e164}")
                return True, "sent"
            print(f"[SMS] Twilio {resp.status_code}: {resp.text}")
            return False, f"Twilio a refusé l'envoi vers {e164}."
        except requests.RequestException as e:
            print(f"[SMS] erreur réseau: {e}")
            return False, "Impossible de joindre le service SMS."

    if cfg["debug"]:
        print(f"[SMS][DEMO] destinataire {e164} — OTP envoyé")
        return True, "demo"

    return False, (
        f"Destinataire reconnu: {e164}. "
        "Configure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN et TWILIO_FROM "
        "dans backend/sms_config.py pour envoyer un vrai SMS."
    )
