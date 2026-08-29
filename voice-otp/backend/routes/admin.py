import hashlib
import hmac
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address

from admin_config import ADMIN_API_KEY
from db import (
    cleanup_older_than_days,
    channel_stats,
    count_events,
    counts_by_channel_and_status,
    dashboard_payload,
    funnel,
    heatmap,
    live_traffic,
    log_event,
    overview_kpis,
    partner_request_totals,
    partner_usage_stats,
    query_events,
    recent_events,
    sparkline_24h,
    status_stats,
    success_rate_24h,
    timeseries,
    top_users,
)
from partners import (
    PLANS,
    activate_account,
    create_account,
    delete_account,
    ensure_test_key,
    get_account,
    list_accounts,
    partner_balances,
    partner_stats,
    renew_access,
    revoke_account,
    rotate_key,
    rotate_test_key,
    update_account,
)
from otp.partner_flow import send_otp, verify_for_partner
from otp.security import limiter
from otp.deliver import deliver_email, deliver_sms, deliver_voice, deliver_whatsapp
from otp.generator import (
    active_otp_count,
    flush_otp_keys,
    generate_otp,
    redis_tool_status,
    store_otp,
    store_whatsapp_pending,
)
from system_settings import get_settings, update_settings

admin_bp = Blueprint("admin", __name__)


def _partner_controls(data):
    extra = {}
    for key in (
        "allow_voice",
        "allow_sms",
        "allow_whatsapp",
        "allow_email",
        "allowed_ip",
        "allowed_prefixes",
    ):
        if key in data:
            extra[key] = data.get(key)
    return extra


def _ip():
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or (request.remote_addr or "")


def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        provided = (request.headers.get("X-Admin-Key") or "").encode("utf-8")
        expected = (ADMIN_API_KEY or "").encode("utf-8")
        digest_a = hashlib.sha256(provided).digest()
        digest_b = hashlib.sha256(expected).digest()
        if not hmac.compare_digest(digest_a, digest_b) or not provided:
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)

    return wrapped


@admin_bp.route("/admin/stats", methods=["GET"])
@require_admin
def stats():
    by_channel, by_status = counts_by_channel_and_status()
    return jsonify({
        "total_requests": count_events(),
        "active_codes": active_otp_count(),
        "success_rate": success_rate_24h(),
        "by_channel": by_channel,
        "by_status": by_status,
    }), 200


@admin_bp.route("/admin/stats/dashboard", methods=["GET"])
@require_admin
def stats_dashboard():
    payload = dashboard_payload()
    payload["kpis"]["active_codes"] = active_otp_count()
    payload["redis"] = redis_tool_status()
    return jsonify(payload), 200


@admin_bp.route("/admin/stats/overview", methods=["GET"])
@require_admin
def stats_overview():
    kpis = overview_kpis()
    kpis["active_codes"] = active_otp_count()
    return jsonify(kpis), 200


@admin_bp.route("/admin/stats/timeseries", methods=["GET"])
@require_admin
def stats_timeseries():
    return jsonify(timeseries(
        days=request.args.get("days", 7),
        granularity=request.args.get("granularity", "day"),
    )), 200


@admin_bp.route("/admin/stats/channels", methods=["GET"])
@require_admin
def stats_channels():
    return jsonify(channel_stats(days=request.args.get("days", 7))), 200


@admin_bp.route("/admin/stats/status", methods=["GET"])
@require_admin
def stats_status():
    return jsonify(status_stats(days=request.args.get("days", 7))), 200


@admin_bp.route("/admin/stats/funnel", methods=["GET"])
@require_admin
def stats_funnel():
    return jsonify(funnel(days=request.args.get("days", 7))), 200


@admin_bp.route("/admin/stats/heatmap", methods=["GET"])
@require_admin
def stats_heatmap():
    return jsonify(heatmap(days=request.args.get("days", 7))), 200


@admin_bp.route("/admin/stats/top-users", methods=["GET"])
@require_admin
def stats_top_users():
    return jsonify(top_users(
        days=request.args.get("days", 7),
        limit=request.args.get("limit", 8),
    )), 200


@admin_bp.route("/admin/stats/sparkline", methods=["GET"])
@require_admin
def stats_sparkline():
    return jsonify(sparkline_24h()), 200


@admin_bp.route("/admin/recent-requests", methods=["GET"])
@require_admin
def recent_requests():
    return jsonify({"results": recent_events(20)}), 200


@admin_bp.route("/admin/traffic/live", methods=["GET"])
@require_admin
def traffic_live():
    limit = request.args.get("limit", 50)
    include_test = str(request.args.get("include_test", "1")).strip().lower() not in (
        "0", "false", "no",
    )
    partner_id = request.args.get("partner_id")
    payload = live_traffic(
        limit,
        include_test=include_test,
        partner_id=partner_id if partner_id not in (None, "", "all") else None,
    )
    payload["settings"] = get_settings()
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return jsonify(payload), 200


@admin_bp.route("/admin/settings", methods=["GET"])
@require_admin
def settings_get():
    return jsonify(get_settings()), 200


@admin_bp.route("/admin/settings", methods=["PATCH", "POST"])
@require_admin
def settings_update():
    data = request.get_json(silent=True) or {}
    payload = update_settings(
        is_maintenance=data.get("is_maintenance") if "is_maintenance" in data else None,
        maintenance_detail=data.get("maintenance_detail") if "maintenance_detail" in data else None,
        allowed_country_prefixes=(
            data.get("allowed_country_prefixes")
            if "allowed_country_prefixes" in data
            else None
        ),
    )
    return jsonify(payload), 200


@admin_bp.route("/admin/logs", methods=["GET"])
@require_admin
def logs():
    payload = query_events(
        channel=request.args.get("channel"),
        status=request.args.get("status"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        page=request.args.get("page", 1),
        page_size=request.args.get("page_size", 20),
    )
    return jsonify(payload), 200


@admin_bp.route("/admin/tools/redis-status", methods=["GET"])
@require_admin
def redis_status():
    return jsonify(redis_tool_status()), 200


@admin_bp.route("/admin/tools/flush-redis", methods=["POST"])
@require_admin
def flush_redis():
    removed = flush_otp_keys()
    return jsonify({"status": "flushed", "keys_removed": removed}), 200


@admin_bp.route("/admin/tools/test-otp", methods=["POST"])
@require_admin
def test_otp():
    data = request.get_json(silent=True) or {}
    channel = (data.get("channel") or "").strip().lower()
    destination = (data.get("destination") or "").strip()
    if channel not in ("voice", "email", "sms", "whatsapp"):
        return jsonify({"status": "error", "detail": "channel doit être voice, email, sms ou whatsapp"}), 400
    if channel != "voice" and not destination:
        return jsonify({"status": "error", "detail": "destination requise"}), 400

    user_id = "admin-test"
    dest = destination or "1000"

    if channel == "whatsapp":
        ok, err = deliver_whatsapp(dest)
        if not ok:
            log_event(user_id, channel, dest, "failed", _ip())
            return jsonify({"status": "error", "detail": str(err)}), 502
        store_whatsapp_pending(user_id, dest)
        log_event(user_id, channel, dest, "sent", _ip())
        return jsonify({"status": "sent", "channel": channel, "userId": user_id}), 200

    otp = generate_otp()

    if channel == "email":
        ok, err = deliver_email(dest, otp)
    elif channel == "sms":
        ok, err = deliver_sms(dest, otp)
    else:
        ok, err = deliver_voice(otp, dest if dest else "1000")

    if not ok:
        log_event(user_id, channel, dest, "failed", _ip())
        return jsonify({"status": "error", "detail": str(err)}), 502

    store_otp(user_id, otp)
    log_event(user_id, channel, dest, "sent", _ip())
    return jsonify({"status": "sent", "channel": channel, "userId": user_id}), 200


@admin_bp.route("/admin/partners/stats", methods=["GET"])
@require_admin
def partners_stats():
    return jsonify(partner_stats()), 200


@admin_bp.route("/admin/partners/balances", methods=["GET"])
@require_admin
def partners_balances():
    return jsonify(partner_balances()), 200


@admin_bp.route("/admin/partners", methods=["GET"])
@require_admin
def partners_index():
    accounts = list_accounts(include_email=True)
    totals = partner_request_totals()
    for item in accounts:
        item["request_total"] = totals.get(item["id"], 0)
    return jsonify({
        "plans": PLANS,
        "accounts": accounts,
    }), 200


@admin_bp.route("/admin/partners/<int:account_id>", methods=["GET"])
@require_admin
def partners_show(account_id):
    partner = get_account(account_id)
    if not partner:
        return jsonify({"status": "error", "detail": "compte_introuvable"}), 404
    return jsonify({
        "account": partner,
        "usage": partner_usage_stats(account_id, days=request.args.get("days", 14)),
    }), 200


@admin_bp.route("/admin/partners/<int:account_id>/stats", methods=["GET"])
@require_admin
def partners_usage(account_id):
    if not get_account(account_id):
        return jsonify({"status": "error", "detail": "compte_introuvable"}), 404
    return jsonify(partner_usage_stats(account_id, days=request.args.get("days", 14))), 200


@admin_bp.route("/admin/partners", methods=["POST"])
@require_admin
def partners_create():
    data = request.get_json(silent=True) or {}
    payload, err = create_account(
        data.get("name"),
        data.get("email"),
        data.get("plan") or "starter",
        data.get("days") or data.get("grant_days"),
        **_partner_controls(data),
    )
    if err:
        return jsonify({"status": "error", "detail": err}), 400
    return jsonify({
        "status": "created",
        "warning": "Copiez api_key (sk_live_) et test_api_key (sk_test_) maintenant. Elles ne seront plus jamais affichées.",
        **payload,
    }), 201


@admin_bp.route("/admin/partners/<int:account_id>/revoke", methods=["POST"])
@require_admin
def partners_revoke(account_id):
    if not revoke_account(account_id):
        return jsonify({"status": "error", "detail": "compte_introuvable"}), 404
    return jsonify({"status": "revoked", "id": account_id}), 200


@admin_bp.route("/admin/partners/<int:account_id>", methods=["DELETE"])
@admin_bp.route("/admin/partners/<int:account_id>/delete", methods=["POST"])
@require_admin
def partners_delete(account_id):
    if not delete_account(account_id):
        return jsonify({"status": "error", "detail": "compte_introuvable"}), 404
    return jsonify({"status": "deleted", "id": account_id}), 200


@admin_bp.route("/admin/partners/<int:account_id>/renew", methods=["POST"])
@require_admin
def partners_renew(account_id):
    data = request.get_json(silent=True) or {}
    partner, err = renew_access(account_id, data.get("days"))
    if err == "compte_introuvable":
        return jsonify({"status": "error", "detail": err}), 404
    if err:
        return jsonify({"status": "error", "detail": err}), 400
    return jsonify({
        "status": "renewed",
        "account": partner,
        "access_until": partner.get("access_until"),
        "days_left": partner.get("days_left"),
    }), 200


@admin_bp.route("/admin/partners/<int:account_id>/activate", methods=["POST"])
@require_admin
def partners_activate(account_id):
    if not activate_account(account_id):
        return jsonify({"status": "error", "detail": "compte_introuvable"}), 404
    return jsonify({"status": "active", "id": account_id}), 200


@admin_bp.route("/admin/partners/<int:account_id>/update", methods=["POST"])
@require_admin
def partners_update(account_id):
    data = request.get_json(silent=True) or {}
    partner, err = update_account(
        account_id,
        name=data.get("name"),
        email=data.get("email"),
        plan=data.get("plan"),
        **_partner_controls(data),
    )
    if err == "compte_introuvable":
        return jsonify({"status": "error", "detail": err}), 404
    if err:
        return jsonify({"status": "error", "detail": err}), 400
    return jsonify({"status": "updated", "account": partner}), 200


@admin_bp.route("/admin/partners/<int:account_id>/rotate", methods=["POST"])
@require_admin
def partners_rotate(account_id):
    payload, err = rotate_key(account_id)
    if err == "compte_introuvable":
        return jsonify({"status": "error", "detail": err}), 404
    if err:
        return jsonify({"status": "error", "detail": err}), 400
    return jsonify({
        "status": "rotated",
        "warning": "Anciennes clés invalidées. Copiez api_key (sk_live_) et test_api_key (sk_test_) maintenant.",
        **payload,
    }), 200


def _sandbox_limit_key():
    args = request.view_args or {}
    if args.get("account_id") is not None:
        return f"sandbox:{args['account_id']}"
    return get_remote_address()


@admin_bp.route("/admin/partners/<int:account_id>/ensure-test-key", methods=["POST"])
@require_admin
def partners_ensure_test_key(account_id):
    payload, err = ensure_test_key(account_id)
    if err == "compte_introuvable":
        return jsonify({"status": "error", "detail": err}), 404
    if err:
        return jsonify({"status": "error", "detail": err}), 400
    return jsonify({"status": "ok", **payload}), 200


@admin_bp.route("/admin/partners/<int:account_id>/rotate-test", methods=["POST"])
@require_admin
def partners_rotate_test(account_id):
    payload, err = rotate_test_key(account_id)
    if err == "compte_introuvable":
        return jsonify({"status": "error", "detail": err}), 404
    if err:
        return jsonify({"status": "error", "detail": err}), 400
    return jsonify({
        "status": "rotated",
        "warning": "Ancienne clé de test invalidée. Copiez test_api_key maintenant.",
        **payload,
    }), 200


@admin_bp.route("/admin/partners/<int:account_id>/sandbox", methods=["POST"])
@require_admin
@limiter.limit("10 per 5 minutes", key_func=_sandbox_limit_key)
def partners_sandbox(account_id):
    partner = get_account(account_id)
    if not partner:
        return jsonify({"status": "error", "detail": "compte_introuvable"}), 404
    if partner.get("status") != "active":
        return jsonify({"status": "error", "detail": "account_revoked"}), 403
    partner["key_mode"] = "test"
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "send").strip().lower()
    if action == "verify":
        payload, status = verify_for_partner(partner, data, _ip())
        return jsonify(payload), status
    channel = (data.get("channel") or "").strip().lower()
    payload, status = send_otp(partner, channel, data, _ip())
    return jsonify(payload), status


@admin_bp.route("/admin/tools/cleanup", methods=["POST"])
@require_admin
def cleanup():
    removed = cleanup_older_than_days(30)
    return jsonify({"status": "cleaned", "rows_removed": removed}), 200
