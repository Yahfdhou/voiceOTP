from flask import Blueprint, jsonify, request

from ai.config import ASK_MAX_CHARS
from ai.copilot import answer_question
from ai.jobs import get_control_center, refresh_snapshot
from otp.security import limiter
from routes.admin import require_admin

ai_bp = Blueprint("ai", __name__)


def _strip_sensitive(text):
    return (text or "").strip()[:ASK_MAX_CHARS]


@ai_bp.route("/admin/ai/status", methods=["GET"])
@require_admin
def status():
    from ai.providers import ollama_status
    data = get_control_center()
    llm = data.get("llm") or {}
    live = ollama_status()
    return jsonify({
        "provider": data.get("provider") or llm.get("provider"),
        "model": live.get("model") or llm.get("model"),
        "online": bool(live.get("online")),
        "model_ready": bool(live.get("model_ready")),
        "models": live.get("models") or [],
        "anomaly_model": (data.get("anomaly") or {}).get("model"),
        "generated_at": data.get("generated_at"),
    }), 200


@ai_bp.route("/admin/ai/control-center", methods=["GET"])
@require_admin
def control_center():
    force = (request.args.get("refresh") or "").lower() in ("1", "true", "yes")
    return jsonify(get_control_center(force=force)), 200


@ai_bp.route("/admin/ai/insights", methods=["GET"])
@require_admin
def insights():
    data = get_control_center()
    return jsonify(data.get("insights") or {}), 200


@ai_bp.route("/admin/ai/anomalies", methods=["GET"])
@require_admin
def anomalies():
    data = get_control_center()
    return jsonify({
        **(data.get("anomaly") or {}),
        "results": data.get("anomalies") or [],
    }), 200


@ai_bp.route("/admin/ai/predictions", methods=["GET"])
@require_admin
def predictions():
    data = get_control_center()
    return jsonify({"results": data.get("predictions") or []}), 200


@ai_bp.route("/admin/ai/recommendations", methods=["GET"])
@require_admin
def recommendations():
    data = get_control_center()
    return jsonify({"results": data.get("recommendations") or []}), 200


@ai_bp.route("/admin/ai/daily-summary", methods=["GET"])
@require_admin
def daily_summary():
    data = get_control_center()
    return jsonify(data.get("daily_summary") or {}), 200


@ai_bp.route("/admin/ai/channels", methods=["GET"])
@require_admin
def channels():
    data = get_control_center()
    return jsonify({"results": data.get("channels") or []}), 200


@ai_bp.route("/admin/ai/health", methods=["GET"])
@require_admin
def health():
    data = get_control_center()
    return jsonify(data.get("health") or {}), 200


@ai_bp.route("/admin/ai/notifications", methods=["GET"])
@require_admin
def notifications():
    data = get_control_center()
    return jsonify({"results": data.get("notifications") or []}), 200


@ai_bp.route("/admin/ai/ask", methods=["POST"])
@require_admin
@limiter.limit("10 per minute")
def ask():
    body = request.get_json(silent=True) or {}
    question = _strip_sensitive(body.get("question") or body.get("message") or "")
    if not question:
        return jsonify({"error": "missing_question"}), 400
    result = answer_question(question)
    return jsonify(result), 200


@ai_bp.route("/admin/ai/guide", methods=["GET"])
@require_admin
def guide():
    from ai.guide import build_guide, get_section

    section = (request.args.get("section") or "").strip()
    guide_data = build_guide()
    if not section:
        return jsonify(guide_data), 200
    item, _ = get_section(section, None)
    if not item:
        return jsonify({
            "error": "unknown_section",
            "allowed": list(guide_data["sections"].keys()),
        }), 404
    return jsonify(item), 200


@ai_bp.route("/admin/ai/guide/audio", methods=["GET"])
@require_admin
@limiter.limit("8 per minute")
def guide_audio():
    from flask import send_file

    from ai.guide import get_section
    from ai.voiceover import synthesize_french

    section = (request.args.get("section") or "full").strip()
    item, guide_data = get_section(section)
    if not item:
        return jsonify({
            "error": "unknown_section",
            "allowed": list(guide_data["sections"].keys()),
        }), 404
    try:
        wav = synthesize_french(item["script"])
    except Exception as exc:
        return jsonify({
            "error": "tts_failed",
            "detail": str(exc)[:200],
            "fallback": "Use the script with the browser SpeechSynthesis API, lang fr-FR.",
            "script": item["script"],
        }), 503
    return send_file(
        wav,
        mimetype="audio/wav",
        as_attachment=False,
        download_name=f"otp-guide-{item['id']}.wav",
    )


@ai_bp.route("/admin/ai/refresh", methods=["POST"])
@require_admin
def refresh():
    payload = refresh_snapshot()
    return jsonify({
        "status": "refreshed",
        "generated_at": payload.get("generated_at"),
        "provider": payload.get("provider"),
        "llm": payload.get("llm") or {},
    }), 200
