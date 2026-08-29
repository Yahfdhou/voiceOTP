import hashlib
import hmac
from functools import wraps

from flask import Blueprint, jsonify, request

from admin_config import ADMIN_API_KEY
from otp.generator import OTP_TTL
from otp.partner_flow import send_otp, verify_for_partner
from otp.security import (
    MAX_VERIFY_ATTEMPTS,
    VERIFY_REQUEST_LIMIT,
    client_ip,
    limiter,
    otp_send_limit,
)
from partners import (
    PLANS,
    access_ok,
    channel_enabled,
    create_account,
    find_by_api_key,
    ip_authorized,
    list_accounts,
    quota_ok,
    revoke_account,
    touch_last_used,
)
from product_config import PRODUCT_BASE, PRODUCT_NAME
from system_settings import get_settings, is_maintenance

v1_bp = Blueprint("v1", __name__)


@v1_bp.before_request
def _maintenance_gate():
    path = request.path or ""
    if not path.startswith("/v1/otp"):
        return None
    if not is_maintenance():
        return None
    detail = (
        get_settings().get("maintenance_detail")
        or "Gateway is under scheduled maintenance"
    )
    return jsonify({
        "error": "system_maintenance",
        "detail": detail,
        "status": "error",
    }), 503


def _ip():
    return client_ip()


def _json():
    return request.get_json(silent=True) or {}


def _partner_key():
    # Header uniquement — jamais en query string (logs / Referer).
    return (request.headers.get("X-Api-Key") or "").strip()


def _admin_ok():
    provided = (request.headers.get("X-Admin-Key") or "").strip().encode("utf-8")
    expected = (ADMIN_API_KEY or "").encode("utf-8")
    if not provided or not expected:
        return False
    return hmac.compare_digest(
        hashlib.sha256(provided).digest(),
        hashlib.sha256(expected).digest(),
    )


def require_partner(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        raw = _partner_key()
        match = find_by_api_key(raw)
        if not match:
            return jsonify({
                "status": "error",
                "detail": "invalid_api_key",
                "hint": "Créez un compte sur /v1/accounts puis envoyez X-Api-Key.",
            }), 401
        if match.get("status") != "active":
            return jsonify({
                "status": "error",
                "detail": "account_revoked",
            }), 403
        if not access_ok(match):
            return jsonify({
                "status": "error",
                "detail": "subscription_expired",
                "access_until": match.get("access_until") or "",
                "days_left": match.get("days_left"),
                "hint": "Le mois d'accès est terminé. L'administrateur doit renouveler après paiement.",
            }), 403
        if not ip_authorized(match, _ip()):
            from db import log_event
            log_event(
                "-",
                "-",
                "-",
                "ip_unauthorized",
                _ip(),
                match.get("id"),
                is_test=match.get("key_mode") == "test",
            )
            return jsonify({
                "error": "ip_unauthorized",
                "status": "error",
                "detail": "ip_unauthorized",
            }), 403
        request.partner = match
        touch_last_used(match["id"])
        return view(*args, **kwargs)

    return wrapped


def require_channel(channel):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            partner = getattr(request, "partner", None) or {}
            if not channel_enabled(partner, channel):
                from db import log_event
                log_event(
                    "-",
                    channel,
                    "-",
                    "channel_disabled_for_account",
                    _ip(),
                    partner.get("id"),
                    is_test=partner.get("key_mode") == "test",
                )
                return jsonify({
                    "error": "channel_disabled_for_account",
                    "status": "error",
                    "detail": "channel_disabled_for_account",
                    "channel": channel,
                    "plan": partner.get("plan"),
                }), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def require_quota(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        partner = getattr(request, "partner", None) or {}
        if partner.get("key_mode") == "test":
            return view(*args, **kwargs)
        if not quota_ok(partner):
            return jsonify({
                "status": "error",
                "detail": "quota_exceeded",
                "plan": partner.get("plan"),
                "daily_quota": partner.get("daily_quota"),
            }), 429
        return view(*args, **kwargs)

    return wrapped


def _error(detail, status=400, **extra):
    payload = {"status": "error", "detail": detail}
    payload.update(extra)
    return jsonify(payload), status


def _public_base():
    root = (request.url_root or PRODUCT_BASE or "").rstrip("/")
    return root or PRODUCT_BASE


def _formula():
    base = _public_base()
    return {
        "product": PRODUCT_NAME,
        "version": "v1",
        "ttl_seconds": OTP_TTL,
        "max_verify_attempts": MAX_VERIFY_ATTEMPTS,
        "base_url": base,
        "docs": f"{base}/v1/docs",
        "accounts": f"{base}/v1/accounts",
        "embed": f"{base}/v1/embed",
        "auth": {
            "header": "X-Api-Key",
            "account": "Un compte partenaire par système externe. Deux clés : sk_live_ (production) et sk_test_ (développement).",
            "note": "sk_test_ n'affecte ni le quota ni les statistiques. Ne jamais exposer sk_live_ dans une application mobile publique.",
        },
        "flow": [
            "Le système externe POST un canal (voice | sms | whatsapp | email) avec userId.",
            "L'utilisateur reçoit le code (appel, SMS ou e-mail).",
            "Le système externe POST /v1/otp/verify avec le même userId et le code saisi.",
            "Si ok=true, continuer le paiement / login. Sinon refuser.",
        ],
        "channels": [
            {
                "id": "voice",
                "method": "POST",
                "path": "/v1/otp/voice",
                "url": f"{base}/v1/otp/voice",
                "body": {"userId": "string", "phoneNumber": "+222XXXXXXXX"},
                "success": {"status": "sent", "channel": "voice", "expiresIn": OTP_TTL},
            },
            {
                "id": "sms",
                "method": "POST",
                "path": "/v1/otp/sms",
                "url": f"{base}/v1/otp/sms",
                "body": {"userId": "string", "phoneNumber": "+222XXXXXXXX"},
                "success": {"status": "sent", "channel": "sms", "expiresIn": OTP_TTL},
            },
            {
                "id": "whatsapp",
                "method": "POST",
                "path": "/v1/otp/whatsapp",
                "url": f"{base}/v1/otp/whatsapp",
                "body": {"userId": "string", "phoneNumber": "+222XXXXXXXX"},
                "success": {"status": "sent", "channel": "whatsapp", "expiresIn": OTP_TTL},
                "note": "Livraison ChinqIT WhatsApp. Le code n'est jamais renvoyé.",
            },
            {
                "id": "email",
                "method": "POST",
                "path": "/v1/otp/email",
                "url": f"{base}/v1/otp/email",
                "body": {"userId": "string", "email": "user@example.com"},
                "success": {"status": "sent", "channel": "email", "expiresIn": OTP_TTL},
            },
        ],
        "verify": {
            "method": "POST",
            "path": "/v1/otp/verify",
            "url": f"{base}/v1/otp/verify",
            "body": {"userId": "string", "otp": "123456"},
            "success": {"ok": True, "channel": "sms"},
            "note": "Un seul verify pour tous les canaux. Le code n'est jamais renvoyé.",
        },
        "errors": {
            "400": "Body incomplet, otp invalid / expired / missing",
            "401": "invalid_api_key",
            "403": "channel_not_in_plan",
            "429": "quota_exceeded (sk_live_) ou rate limit (20/5 min live, 10/5 min test)",
            "502": "canal indisponible",
        },
        "security": [
            {
                "id": "api_key",
                "title": "X-Api-Key",
                "detail": "Authentification partenaire, comparaison SHA-256 + compare_digest.",
            },
            {
                "id": "plans",
                "title": "Contrôle des canaux",
                "detail": "403 si le canal n'est pas dans le plan (starter = sms+whatsapp+email).",
            },
            {
                "id": "hashed_otp",
                "title": "OTP hashé",
                "detail": "HMAC-SHA256 en Redis, jamais le code en clair ni dans le JSON.",
            },
            {
                "id": "csprng",
                "title": "Génération crypto",
                "detail": "6 chiffres via secrets (CSPRNG).",
            },
            {
                "id": "ttl",
                "title": "Expiration 180 s",
                "detail": "SETEX Redis, disparition automatique.",
            },
            {
                "id": "one_time",
                "title": "Usage unique",
                "detail": "Le hash est effacé après verify réussi.",
            },
            {
                "id": "brute_force",
                "title": "Anti brute-force",
                "detail": "3 essais max puis 429 et suppression du code.",
            },
            {
                "id": "quota",
                "title": "Quota journalier",
                "detail": "Limite par plan (starter 100, pro 1000, business 5000). Les clés sk_test_ ne consomment pas le quota.",
            },
            {
                "id": "hashed_keys",
                "title": "Clés hashées",
                "detail": "sk_live_ et sk_test_ sont hashées SHA-256. Jamais stockées en clair. Affichées une seule fois à la création ou à la régénération.",
            },
            {
                "id": "admin_key",
                "title": "Admin séparé",
                "detail": "X-Admin-Key pour le dashboard, distinct de X-Api-Key.",
            },
            {
                "id": "audit",
                "title": "Journal",
                "detail": "Événements canal/statut/IP sans stocker l'OTP.",
            },
        ],
    }


@v1_bp.route("/v1", methods=["GET"])
def catalog():
    return jsonify(_formula()), 200


@v1_bp.route("/v1/formula", methods=["GET"])
def formula_page():
    return jsonify(_formula()), 200


@v1_bp.route("/v1/docs", methods=["GET"])
def docs_page():
    payload = _formula()
    payload["admin_ui"] = "Dashboard Nuxt · /integration · /accounts · /widget"
    return jsonify(payload), 200


@v1_bp.route("/v1/embed", methods=["GET"])
def embed_page():
    return jsonify({
        "status": "moved",
        "detail": "Le widget est dans le dashboard Nuxt, page /widget.",
    }), 200


@v1_bp.route("/v1/accounts/list", methods=["GET"])
def accounts_list():
    if not _admin_ok():
        return jsonify({"status": "error", "detail": "unauthorized"}), 401
    return jsonify({
        "plans": PLANS,
        "accounts": list_accounts(include_email=True),
    }), 200


@v1_bp.route("/v1/accounts", methods=["POST"])
@limiter.limit("20 per hour")
def accounts_create():
    if not _admin_ok():
        return jsonify({
            "status": "error",
            "detail": "unauthorized",
            "hint": "Seul l'admin crée les comptes (X-Admin-Key).",
        }), 401
    data = _json()
    plan = (data.get("plan") or "starter").strip().lower()
    payload, err = create_account(
        data.get("name"),
        data.get("email"),
        plan,
    )
    if err:
        return _error(err, 400)
    return jsonify({
        "status": "created",
        "warning": "Copiez api_key (sk_live_) et test_api_key (sk_test_) maintenant. Elles ne seront plus jamais affichées.",
        **payload,
    }), 201


@v1_bp.route("/v1/accounts/<int:account_id>/revoke", methods=["POST"])
def accounts_revoke(account_id):
    if not _admin_ok():
        return jsonify({"status": "error", "detail": "unauthorized"}), 401
    if not revoke_account(account_id):
        return _error("compte_introuvable", 404)
    return jsonify({"status": "revoked", "id": account_id}), 200


@v1_bp.route("/v1/me", methods=["GET"])
@require_partner
def account_me():
    partner = request.partner
    return jsonify({
        "account": {
            "name": partner["name"],
            "plan": partner["plan"],
            "channels": partner["channels"],
            "status": partner["status"],
            "daily_quota": partner["daily_quota"],
            "used_today": partner["used_today"],
            "key_mode": partner.get("key_mode") or "live",
        }
    }), 200


@v1_bp.route("/v1/otp/voice", methods=["POST"])
@require_partner
@require_channel("voice")
@require_quota
@limiter.limit(otp_send_limit)
def send_voice():
    payload, status = send_otp(request.partner, "voice", _json(), _ip())
    return jsonify(payload), status


@v1_bp.route("/v1/otp/sms", methods=["POST"])
@require_partner
@require_channel("sms")
@require_quota
@limiter.limit(otp_send_limit)
def send_sms():
    payload, status = send_otp(request.partner, "sms", _json(), _ip())
    return jsonify(payload), status


@v1_bp.route("/v1/otp/whatsapp", methods=["POST"])
@require_partner
@require_channel("whatsapp")
@require_quota
@limiter.limit(otp_send_limit)
def send_whatsapp():
    payload, status = send_otp(request.partner, "whatsapp", _json(), _ip())
    return jsonify(payload), status


@v1_bp.route("/v1/otp/email", methods=["POST"])
@require_partner
@require_channel("email")
@require_quota
@limiter.limit(otp_send_limit)
def send_email():
    payload, status = send_otp(request.partner, "email", _json(), _ip())
    return jsonify(payload), status


@v1_bp.route("/v1/otp/verify", methods=["POST"])
@require_partner
@limiter.limit(VERIFY_REQUEST_LIMIT)
def verify():
    payload, status = verify_for_partner(request.partner, _json(), _ip())
    return jsonify(payload), status
