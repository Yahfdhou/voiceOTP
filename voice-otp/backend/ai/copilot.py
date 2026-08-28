from ai.jobs import get_control_center
from ai.features import llm_safe_context, build_features
from ai.narrate import generate_copilot_answer


def answer_question(question):
    question = (question or "").strip()
    if not question:
        return {
            "answer": "Posez une question sur le système OTP.",
            "provider": "none",
        }
    features = build_features(hours=48)
    context = llm_safe_context(features)
    snapshot = get_control_center()
    context = {
        **context,
        "health": snapshot["health"],
        "anomaly": {
            "detected": snapshot["anomaly"]["detected"],
            "risk_level": snapshot["anomaly"]["risk_level"],
            "anomaly_score": snapshot["anomaly"]["anomaly_score"],
            "reasons": snapshot["anomaly"]["reasons"],
            "model": snapshot["anomaly"].get("model"),
        },
        "recommendations": [r["text"] for r in snapshot.get("recommendations") or []],
    }
    text, provider, model = generate_copilot_answer(question[:500], context)
    if not text:
        text = _fallback_answer(question, context)
        provider = "template"
        model = None
    return {
        "answer": text,
        "provider": provider,
        "model": model,
        "source": provider,
        "context_used": context,
    }


def _fallback_answer(question, context):
    if context.get("insufficient_data"):
        return "Les données disponibles sont insuffisantes pour répondre avec certitude."
    q = question.lower()
    totals = context.get("totals") or {}
    sms = context.get("sms") or {}
    voice = context.get("voice") or {}
    email = context.get("email") or {}
    if "sms" in q and ("pourquoi" in q or "why" in q or "diminu" in q or "échec" in q or "echec" in q):
        return (
            f"SMS 24h: {sms.get('requests', 0)} requêtes, succès {sms.get('success_rate', 0)}%, "
            f"échecs {sms.get('failure_rate', 0)}%. "
            f"Voice: succès {voice.get('success_rate', 0)}%. "
            f"Santé: {context.get('health', {}).get('score')}."
        )
    if "compar" in q:
        return (
            f"SMS reliability {sms.get('reliability', 0)}%, "
            f"Voice {voice.get('reliability', 0)}%, "
            f"Email {email.get('reliability', 0)}%."
        )
    if "anomal" in q:
        anom = context.get("anomaly") or {}
        if not anom.get("detected"):
            return "Aucune anomalie majeure n'a été détectée sur la fenêtre récente."
        return "Anomalies: " + "; ".join(anom.get("reasons") or [])
    if "fiable" in q or "reliable" in q:
        blocks = [("sms", sms), ("whatsapp", context.get("whatsapp") or {}), ("voice", voice), ("email", email)]
        live = [b for b in blocks if (b[1] or {}).get("requests", 0) > 0]
        if not live:
            return "Les données disponibles sont insuffisantes pour répondre avec certitude."
        best = max(live, key=lambda b: b[1].get("reliability") or 0)
        return f"Le canal le plus fiable est {best[0]} ({best[1].get('reliability')}%)."
    return (
        f"Résumé 24h: {totals.get('requests', 0)} événements, "
        f"succès {totals.get('success_rate', 0)}%, "
        f"échecs {totals.get('failure_rate', 0)}%, "
        f"santé {context.get('health', {}).get('score')} / 100, "
        f"risque {context.get('health', {}).get('risk_level')}."
    )
