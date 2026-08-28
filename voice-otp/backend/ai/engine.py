from datetime import datetime, timedelta, timezone

from ai.anomaly import detect_anomalies
from ai.features import build_features, llm_safe_context
from ai.predict import predict_metrics
from ai.providers import get_provider


def _pct_delta(current, previous):
    if previous is None or previous == 0:
        if not current:
            return 0.0
        return None
    return round(((current - previous) / previous) * 100, 1)


def channel_intelligence(features):
    trend = features.get("trend_window") or {}
    hourly = features.get("channel_hourly") or {}
    items = []
    for name, block in (features.get("channels") or {}).items():
        direction = "stable"
        cur = trend.get("current_6h_failure") or 0
        prev = trend.get("previous_6h_failure") or 0
        if block["requests"] == 0:
            direction = "stable"
        elif name == "sms" and cur > prev + 4:
            direction = "down"
        elif block["reliability"] >= 90:
            direction = "up" if prev > cur else "stable"
        spark = hourly.get(name) or []
        items.append({
            **block,
            "success": block.get("verified") or 0,
            "failed": (block.get("failed") or 0) + (block.get("invalid") or 0),
            "trend": spark,
            "trend_label": direction,
            "sparkline": spark,
            "average_response_time": None,
            "response_time_note": "Not collected by the OTP core (kept independent).",
        })
    return items


def health_score(features, anomaly):
    totals = features.get("totals") or {}
    success = totals.get("success_rate") or 0
    failure = totals.get("failure_rate") or 0
    blocked = totals.get("too_many_attempts_rate") or 0
    score = 100.0
    score -= min(40.0, failure * 1.2)
    score -= min(20.0, blocked * 1.5)
    score -= min(25.0, (anomaly.get("anomaly_score") or 0) * 25)
    if success < 20 and totals.get("requests", 0) >= 8:
        score -= 10
    score = round(max(0.0, min(100.0, score)), 1)
    if totals.get("requests", 0) == 0:
        label = "Warning"
        status = "no_data"
    elif score >= 90:
        label = "Excellent"
        status = "healthy"
    elif score >= 75:
        label = "Good"
        status = "healthy"
    elif score >= 55:
        label = "Warning"
        status = "degraded"
    else:
        label = "Critical"
        status = "critical"
    return {
        "score": score,
        "label": label,
        "status": status,
        "risk_level": anomaly.get("risk_level") or "LOW",
    }


def _best_channel(features):
    best = None
    for name, block in (features.get("channels") or {}).items():
        if block["requests"] == 0:
            continue
        if best is None or block["reliability"] > best["reliability"]:
            best = {**block, "channel": name}
    return best


def build_insights(features, anomaly, predictions):
    insights = []
    totals = features.get("totals") or {}
    if anomaly.get("detected"):
        for reason in anomaly.get("reasons") or []:
            insights.append({"level": "warning", "text": reason})
    elif totals.get("requests", 0) > 0:
        insights.append({"level": "ok", "text": "No major anomaly versus recent hours."})

    for item in predictions.get("items") or []:
        if item.get("predicted") is None:
            continue
        if item.get("risk") == "HIGH":
            insights.append({
                "level": "warning",
                "text": (
                    f"{item['channel'].upper()} failure predicted {item['predicted']}% "
                    f"(current {item['current']}%)."
                ),
            })

    best = _best_channel(features)
    if best:
        insights.append({
            "level": "ok",
            "text": f"{best['channel'].capitalize()} is the most reliable channel ({best['reliability']}%).",
        })
    return insights[:8]


def build_insight_card(features, anomaly, insight_items):
    totals = features.get("totals") or {}
    requests = totals.get("requests") or 0
    count = 1 if anomaly.get("detected") else 0
    if not anomaly.get("detected"):
        count = 0
    confidence = 0 if requests == 0 else min(95, 30 + requests * 3)
    return {
        "anomalies_count": count,
        "risk_level": anomaly.get("risk_level") or "LOW",
        "confidence": confidence,
        "items": [item.get("text") for item in insight_items if item.get("text")],
        "message": None,
    }


def build_recommendations(features, anomaly, channels):
    recs = []
    sms = next((c for c in channels if c["channel"] == "sms"), None)
    voice = next((c for c in channels if c["channel"] == "voice"), None)
    if sms and voice and sms["requests"] > 0 and voice["requests"] > 0:
        if sms["reliability"] + 8 < voice["reliability"]:
            recs.append(
                "SMS reliability is below Voice. Consider using Voice temporarily while monitoring SMS."
            )
    if anomaly.get("detected") and anomaly.get("risk_level") == "HIGH":
        recs.append("Investigate the flagged channel before increasing OTP traffic.")
    if (features.get("totals") or {}).get("too_many_attempts_rate", 0) >= 8:
        recs.append("too_many_attempts is elevated. Review brute-force attempts; do not raise the attempt limit.")
    if (features.get("totals") or {}).get("requests", 0) == 0:
        recs.append("No OTP events in the last 24 hours. Send a test OTP to populate the dashboard.")
    elif not recs:
        recs.append("No critical action required. Keep monitoring SMS, Voice and Email.")
    return [{"text": text, "requires_admin_approval": True} for text in recs[:5]]


def build_daily_summary(features, health, anomaly, recs):
    totals = features.get("totals") or {}
    best = _best_channel(features)
    main = None
    if anomaly.get("detected"):
        main = (anomaly.get("reasons") or ["Anomaly detected"])[0]
    affected = None
    worst = None
    for name, block in (features.get("channels") or {}).items():
        if block["requests"] == 0:
            continue
        if worst is None or block["failure_rate"] > worst["failure_rate"]:
            worst = {**block, "channel": name}
    if worst and worst["failure_rate"] >= 8:
        affected = worst["channel"]
    rec_text = recs[0]["text"] if recs else "Monitor the platform."
    requests = totals.get("requests", 0)
    verified = totals.get("verified", 0)
    success = totals.get("success_rate", 0)
    text = (
        f"System Health: {health['score']}% ({health['label']}). "
        f"OTP requests (24h): {requests}. "
        f"Successful verifications: {verified}. "
        f"Success rate: {success}%. "
        f"Main issue: {main or 'None'}. Affected channel: {affected or 'none'}. "
        f"Risk: {health['risk_level']}. Recommendation: {rec_text}"
    )
    return {
        "title": "AI Daily Summary",
        "date": "Dernières 24h",
        "health": health["score"],
        "otp_requests": requests,
        "total_sends": requests,
        "total": requests,
        "successful_verifications": verified,
        "verified": verified,
        "success_rate": success,
        "main_issue": main,
        "affected_channel": affected,
        "best_channel": best["channel"] if best else None,
        "risk": health["risk_level"],
        "risk_level": health["risk_level"],
        "recommendation": rec_text,
        "text": text,
        "provider": "metrics",
        "insufficient_data": requests == 0,
    }


def build_notifications(anomaly, insights):
    notes = []
    if anomaly.get("detected"):
        reason = (anomaly.get("reasons") or ["Unusual behaviour"])[0]
        notes.append({
            "level": "warning",
            "title": "AI detected an anomaly",
            "text": reason,
            "detail": reason,
            "message": reason,
            "reason": reason,
            "risk": anomaly.get("risk_level"),
            "action": "View Analysis",
        })
    for item in insights:
        if item.get("level") == "warning":
            text = item.get("text") or ""
            notes.append({
                "level": "warning",
                "title": "AI insight",
                "text": text,
                "detail": text,
                "message": text,
                "reason": text,
                "risk": anomaly.get("risk_level"),
                "action": "View Analysis",
            })
    return notes[:5]


def build_anomalies_list(anomaly):
    if not anomaly.get("detected"):
        return []
    items = []
    for reason in anomaly.get("reasons") or []:
        items.append({
            "reason": reason,
            "message": reason,
            "detail": reason,
            "score": anomaly.get("anomaly_score"),
            "time": None,
        })
    return items


def build_kpi_block(features, health, anomaly):
    totals = features.get("totals") or {}
    trend = features.get("trend_window") or {}
    hourly = features.get("hourly") or []
    sends = [row.get("requests") or 0 for row in hourly[-24:]]
    success = [row.get("success_rate") or 0 for row in hourly[-24:]]
    failure = [row.get("failure_rate") or 0 for row in hourly[-24:]]
    health_spark = [max(0.0, 100.0 - (row.get("failure_rate") or 0)) for row in hourly[-24:]]
    anomaly_spark = [min(1.0, (row.get("failure_rate") or 0) / 100) for row in hourly[-24:]]
    return {
        "success_rate": totals.get("success_rate") or 0,
        "success_rate_delta": _pct_delta(
            trend.get("current_6h_success") or 0,
            trend.get("previous_6h_success") or 0,
        ),
        "failure_rate": totals.get("failure_rate") or 0,
        "failure_rate_delta": _pct_delta(
            trend.get("current_6h_failure") or 0,
            trend.get("previous_6h_failure") or 0,
        ),
        "total_sends": totals.get("requests") or 0,
        "total_requests": totals.get("requests") or 0,
        "total_sends_delta": _pct_delta(
            trend.get("current_6h_requests") or 0,
            trend.get("previous_6h_requests") or 0,
        ),
        "anomaly_score": anomaly.get("anomaly_score") or 0,
        "anomaly_risk": anomaly.get("risk_level") or "LOW",
        "sparklines": {
            "health": health_spark,
            "success": success,
            "failure": failure,
            "sends": sends,
            "anomaly": anomaly_spark,
        },
    }


def build_timeseries(features):
    try:
        from db import timeseries
        packed = timeseries(days=7, granularity="day")
        return packed.get("points") or []
    except Exception:
        points = []
        for row in features.get("hourly") or []:
            ts = row.get("hour") or ""
            points.append({
                "label": ts[:10] if ts else "",
                "date": ts,
                "total": row.get("requests") or 0,
                "sent": row.get("requests") or 0,
                "verified": row.get("verified") or 0,
                "success": row.get("verified") or 0,
                "failed": (row.get("failed") or 0) + (row.get("invalid") or 0),
            })
        return points


def build_predictions_list(predictions):
    items = []
    for item in predictions.get("items") or []:
        predicted = item.get("predicted")
        if predicted is None:
            predicted = item.get("current")
        items.append({
            **item,
            "failure_rate": predicted,
            "rate": predicted,
            "level": item.get("level") or item.get("risk"),
        })
    return items


def _system_status():
    try:
        from otp.generator import redis_tool_status
        redis = redis_tool_status()
        connected = bool(redis.get("connected"))
    except Exception:
        connected = False
    return {
        "redis": connected,
        "database": "OK",
        "uptime": None,
    }


def _llm_block(provider="template", model=None, status=None):
    status = status or {}
    return {
        "provider": provider,
        "model": model or status.get("model"),
        "online": bool(status.get("online")),
        "model_ready": bool(status.get("model_ready")),
    }


def enrich_with_llm(payload):
    from ai.narrate import generate_dashboard_narrative
    from ai.providers import ollama_status

    status = ollama_status()
    context = payload.get("context") or {}
    safe = {
        **context,
        "health": payload.get("health"),
        "anomaly": {
            "detected": (payload.get("anomaly") or {}).get("detected"),
            "risk_level": (payload.get("anomaly") or {}).get("risk_level"),
            "anomaly_score": (payload.get("anomaly") or {}).get("anomaly_score"),
            "model": (payload.get("anomaly") or {}).get("model"),
            "reasons": (payload.get("anomaly") or {}).get("reasons"),
        },
        "predictions": payload.get("predictions"),
    }
    narrative, provider, model, status = generate_dashboard_narrative(safe)
    payload["llm"] = _llm_block(provider, model, status)
    payload["provider"] = provider
    if not narrative:
        return payload
    insights = payload.get("insights") or {}
    insights["message"] = narrative["analysis"]
    insights["headline"] = narrative["headline"]
    payload["insights"] = insights
    summary = payload.get("daily_summary") or {}
    summary["text"] = narrative["analysis"]
    summary["headline"] = narrative["headline"]
    if narrative.get("main_issue"):
        summary["main_issue"] = narrative["main_issue"]
    payload["daily_summary"] = summary
    if narrative.get("recommendations"):
        payload["recommendations"] = [
            {"text": item, "requires_admin_approval": True, "source": "ollama"}
            for item in narrative["recommendations"]
        ]
    return payload


def compute_control_center():
    from ai.providers import ollama_status

    features = build_features(hours=48)
    anomaly = detect_anomalies(features)
    predictions = predict_metrics(features)
    channels = channel_intelligence(features)
    health = health_score(features, anomaly)
    insight_items = build_insights(features, anomaly, predictions)
    recommendations = build_recommendations(features, anomaly, channels)
    summary = build_daily_summary(features, health, anomaly, recommendations)
    kpis = build_kpi_block(features, health, anomaly)
    empty = bool(features.get("insufficient_data")) or (features.get("totals") or {}).get("requests", 0) == 0
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    period_label = f"{start.strftime('%d/%m/%Y')} → {now.strftime('%d/%m/%Y')}"
    pred_list = build_predictions_list(predictions)
    status = ollama_status()
    return {
        "generated_at": now.isoformat(),
        "provider": get_provider().name,
        "llm": _llm_block(get_provider().name, None, status),
        "insufficient": empty,
        "insufficient_data": empty,
        "ml_ready": bool(features.get("ml_ready")),
        "message": None,
        "period_label": period_label,
        "health": health,
        "health_score": health.get("score"),
        "kpis": kpis,
        "success_rate": kpis["success_rate"],
        "failure_rate": kpis["failure_rate"],
        "total_sends": kpis["total_sends"],
        "total_requests": kpis["total_sends"],
        "anomaly_score": kpis["anomaly_score"],
        "anomaly_risk": kpis["anomaly_risk"],
        "risk_level": health.get("risk_level"),
        "anomaly": anomaly,
        "anomalies": build_anomalies_list(anomaly),
        "predictions": pred_list,
        "channels": channels,
        "timeseries": build_timeseries(features),
        "insights": build_insight_card(features, anomaly, insight_items),
        "recommendations": recommendations,
        "daily_summary": summary,
        "notifications": build_notifications(anomaly, insight_items),
        "system": _system_status(),
        "context": llm_safe_context(features),
    }
