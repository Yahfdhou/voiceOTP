"""OTP vocal via Telnyx TeXML/Call Control — audio hébergé chez Telnyx (pas de RTP local)."""
from __future__ import annotations

import os
import time
import xml.sax.saxutils

import requests

import env_load  # noqa: F401


def _api_key():
    return (os.getenv("TELNYX_API_KEY") or "").strip()


def _from_number():
    return (
        (os.getenv("TELNYX_FROM") or "").strip()
        or (os.getenv("SIP_TRUNK_CALLER_ID") or "").strip()
    )


def _connection_id():
    return (
        (os.getenv("TELNYX_TEXML_APP_ID") or "").strip()
        or (os.getenv("TELNYX_CONNECTION_ID") or "").strip()
    )


def _account_sid():
    return (os.getenv("TELNYX_ACCOUNT_SID") or _connection_id() or "").strip()


def _e164(phone):
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return ""
    return f"+{digits}"


def _spoken_code(otp):
    spaced = ", ".join(list(str(otp)))
    return (
        f"Your verification code is {spaced}. "
        f"I repeat: {spaced}. "
        f"Once more: {spaced}."
    )


def _texml_body(otp):
    text = xml.sax.saxutils.escape(_spoken_code(otp))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Say voice=\"female\">{text}</Say>"
        "<Hangup/>"
        "</Response>"
    )


def _headers():
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _try_texml(to_e164, from_e164, otp):
    app_id = _connection_id()
    account = _account_sid()
    texml = _texml_body(otp)
    attempts = [
        (
            f"https://api.telnyx.com/v2/texml/calls/{app_id}",
            {"From": from_e164, "To": to_e164, "Texml": texml},
        ),
        (
            f"https://api.telnyx.com/v2/texml/Accounts/{account}/Calls",
            {
                "ApplicationSid": app_id,
                "From": from_e164,
                "To": to_e164,
                "Texml": texml,
            },
        ),
    ]
    errors = []
    for url, body in attempts:
        try:
            resp = requests.post(url, json=body, headers=_headers(), timeout=30)
        except requests.exceptions.RequestException as exc:
            errors.append(str(exc))
            continue
        print(f"[TELNYX] TeXML {resp.status_code} {url} {(resp.text or '')[:240]}")
        if resp.status_code in (200, 201):
            return True, None
        errors.append(f"HTTP {resp.status_code}: {(resp.text or '')[:220]}")
    return False, " | ".join(errors)[:400]


def _try_call_control_speak(to_e164, from_e164, otp):
    """Dial Call Control, attendre answered (poll), Speak, Hangup."""
    connection_id = _connection_id()
    create = requests.post(
        "https://api.telnyx.com/v2/calls",
        headers=_headers(),
        json={
            "connection_id": connection_id,
            "to": to_e164,
            "from": from_e164,
            "timeout_secs": 60,
        },
        timeout=30,
    )
    print(f"[TELNYX] dial {create.status_code} {(create.text or '')[:240]}")
    if create.status_code not in (200, 201):
        return False, f"dial HTTP {create.status_code}: {(create.text or '')[:220]}"

    payload = (create.json() or {}).get("data") or {}
    call_id = payload.get("call_control_id") or ""
    if not call_id:
        return False, "call_control_id manquant dans la réponse Telnyx"

    answered = False
    for _ in range(70):
        time.sleep(1)
        status = requests.get(
            f"https://api.telnyx.com/v2/calls/{call_id}",
            headers=_headers(),
            timeout=15,
        )
        if status.status_code != 200:
            continue
        data = (status.json() or {}).get("data") or {}
        state = (data.get("state") or data.get("call_state") or "").lower()
        is_alive = data.get("is_alive")
        print(f"[TELNYX] poll state={state} alive={is_alive}")
        if state in ("answered", "active", "bridged"):
            answered = True
            break
        if state in ("hangup", "ended", "rejected") or is_alive is False:
            return False, f"appel terminé avant réponse (state={state or 'unknown'})"

    if not answered:
        try:
            requests.post(
                f"https://api.telnyx.com/v2/calls/{call_id}/actions/hangup",
                headers=_headers(),
                json={},
                timeout=15,
            )
        except requests.exceptions.RequestException:
            pass
        return False, "pas de réponse (timeout 70s)"

    speak = requests.post(
        f"https://api.telnyx.com/v2/calls/{call_id}/actions/speak",
        headers=_headers(),
        json={
            "payload": _spoken_code(otp),
            "voice": "female",
            "language": "en-US",
        },
        timeout=30,
    )
    print(f"[TELNYX] speak {speak.status_code} {(speak.text or '')[:200]}")
    if speak.status_code not in (200, 201, 202):
        return False, f"speak HTTP {speak.status_code}: {(speak.text or '')[:220]}"

    time.sleep(14)
    try:
        requests.post(
            f"https://api.telnyx.com/v2/calls/{call_id}/actions/hangup",
            headers=_headers(),
            json={},
            timeout=15,
        )
    except requests.exceptions.RequestException:
        pass
    return True, None


def deliver_telnyx_voice(otp, phone_number):
    if not _api_key():
        return False, (
            "TELNYX_API_KEY manquante. Créez une clé API dans Telnyx Mission Control "
            "→ API Keys, puis ajoutez-la dans backend/.env"
        )
    if not _connection_id():
        return False, (
            "TELNYX_TEXML_APP_ID (ou TELNYX_CONNECTION_ID) manquant. "
            "Créez une TeXML / Voice API Application et collez son ID dans .env"
        )
    from_e164 = _e164(_from_number())
    to_e164 = _e164(phone_number)
    if not from_e164.startswith("+1"):
        return False, "TELNYX_FROM / SIP_TRUNK_CALLER_ID doit être le DID +1 acheté"
    if not to_e164:
        return False, "Numéro de téléphone invalide"

    ok, err = _try_texml(to_e164, from_e164, otp)
    if ok:
        return True, None

    ok2, err2 = _try_call_control_speak(to_e164, from_e164, otp)
    if ok2:
        return True, None

    return False, (err2 or err or "échec Telnyx voice")[:400]
