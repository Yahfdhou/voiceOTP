import env_load  # noqa: F401
import os
import socket
import time

import requests

_raw = os.getenv("PBX_ARI_URL", "http://localhost:8088/ari/channels").rstrip("/")
if _raw.endswith("/channels"):
    PBX_CHANNELS = _raw
    PBX_BASE = _raw[: -len("/channels")]
else:
    PBX_BASE = _raw
    PBX_CHANNELS = f"{_raw}/channels"

PBX_USER = os.getenv("PBX_USER", "voiceotp-user")
PBX_PASS = os.getenv("PBX_PASS", "ari-secret-123")


def lan_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "10.134.42.144"


def endpoint_status(endpoint="1000"):
    try:
        resp = requests.get(
            f"{PBX_BASE}/endpoints/PJSIP/{endpoint}",
            auth=(PBX_USER, PBX_PASS),
            timeout=5,
        )
        if resp.status_code != 200:
            return False, resp.text
        data = resp.json()
        state = (data.get("state") or "").lower()
        return state in ("online", "unknown"), data
    except requests.exceptions.RequestException as e:
        return False, str(e)


def _originate(endpoint, otp_code, context, extension, caller_id):
    params = {
        "endpoint": endpoint,
        "context": context,
        "extension": extension,
        "priority": 1,
        "timeout": 45,
        "callerId": caller_id,
    }
    try:
        resp = requests.post(
            PBX_CHANNELS,
            params=params,
            json={"variables": {"CODE": str(otp_code)}},
            auth=(PBX_USER, PBX_PASS),
            timeout=20,
        )
        if resp.status_code in (200, 201):
            return True, resp.json()
        return False, (resp.text or f"ARI HTTP {resp.status_code}")[:400]
    except requests.exceptions.RequestException as e:
        return False, (
            "Asterisk ARI injoignable. Vérifiez que le conteneur Asterisk tourne "
            f"et PBX_ARI_URL ({PBX_BASE}). {e}"
        )


def trigger_call(phone_or_endpoint, otp_code):
    """Labo : appelle l'extension Linphone (défaut 1000)."""
    ok, _info = endpoint_status(phone_or_endpoint)
    if not ok:
        ip = lan_ip()
        return False, (
            f"Linphone n'est pas enregistré. Sur le téléphone (même Wi-Fi) : "
            f"Username 1000, mot de passe changeme123, Domain {ip}, UDP. "
            f"Pas 192.168.100.134. Quand Linphone affiche Connected, réessaie."
        )
    return _originate(
        f"PJSIP/{phone_or_endpoint}",
        otp_code,
        "otp-call",
        "otp-call",
        "VoiceOTP <1000>",
    )


def _local_channel_alive(digits):
    """True si un canal Local/...@otp-trunk-dial est encore actif pour ce numéro."""
    try:
        resp = requests.get(
            f"{PBX_BASE}/channels",
            auth=(PBX_USER, PBX_PASS),
            timeout=5,
        )
        if resp.status_code != 200:
            return False
        needle = f"Local/{digits}@otp-trunk-dial"
        for item in resp.json() or []:
            name = item.get("name") or ""
            if needle in name:
                return True
    except requests.exceptions.RequestException:
        return False
    return False


def trigger_trunk_call(phone_number, otp_code):
    """Production : Local → Dial(PJSIP/+E164@trunk) + U(otp-play). Log DIALSTATUS."""
    from product_config import SIP_TRUNK_CALLER_ID

    digits = "".join(ch for ch in (phone_number or "") if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return False, "Numéro de téléphone invalide"
    # Local ;2 exécute Dial+U(play). Local ;1 attend dans otp-trunk-idle.
    endpoint = f"Local/{digits}@otp-trunk-dial"
    ok, result = _originate(
        endpoint,
        otp_code,
        "otp-trunk-idle",
        "s",
        SIP_TRUNK_CALLER_ID,
    )
    if not ok:
        return False, result

    # Telnyx rejette souvent en <1s (403 / cause 21). ARI renvoie OK trop tôt :
    # on vérifie que le canal Local est encore vivant après un court délai.
    time.sleep(2.5)
    if not _local_channel_alive(digits):
        return False, (
            "Appel rejeté par Telnyx (CHANUNAVAIL / cause 21). "
            "Ouvrez Outbound Voice Profiles et autorisez Africa / Mauritania (+222) "
            "sur le profil lié à la connection voiceotp. "
            "Par défaut seuls USA/Canada sont autorisés."
        )
    return True, result
