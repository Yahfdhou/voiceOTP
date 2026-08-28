from ai.config import MIN_HOURS_FOR_ML


def _normalize(score, lo, hi):
    if hi <= lo:
        return 0.0
    value = (score - lo) / (hi - lo)
    return round(max(0.0, min(1.0, value)), 3)


def detect_anomalies(features):
    hourly = features.get("hourly") or []
    active = [row for row in hourly if row["requests"] > 0]
    reasons = []
    detected = False
    score = 0.0

    totals = features.get("totals") or {}
    trend = features.get("trend_window") or {}
    cur_fail = trend.get("current_6h_failure") or 0
    prev_fail = trend.get("previous_6h_failure") or 0
    if prev_fail > 0 and cur_fail >= prev_fail * 1.4 and cur_fail - prev_fail >= 5:
        detected = True
        score = max(score, 0.72)
        reasons.append(
            f"Failure rate rose from {prev_fail}% to {cur_fail}% over the last 6 hours."
        )
    if totals.get("too_many_attempts_rate", 0) >= 8:
        detected = True
        score = max(score, 0.7)
        reasons.append(
            f"too_many_attempts rate is {totals.get('too_many_attempts_rate')}% in 24h."
        )
    if totals.get("requests_last_hour", 0) >= max(8, (totals.get("requests_per_hour") or 0) * 3):
        detected = True
        score = max(score, 0.65)
        reasons.append("Request volume in the last hour is unusually high versus the 24h average.")

    ml = _isolation_forest(active)
    if ml:
        score = max(score, ml["anomaly_score"])
        if ml["detected"]:
            detected = True
            reasons.extend(ml["reasons"])

    if features.get("insufficient_data"):
        return {
            "detected": False,
            "anomaly_score": 0.0,
            "risk_level": "LOW",
            "model": "insufficient_data",
            "reasons": ["Not enough OTP events in the last 24 hours for anomaly scoring."],
            "insufficient_data": True,
        }

    if not reasons and score < 0.4:
        reasons.append("No unusual deviation versus recent hours.")

    risk = "LOW"
    if score >= 0.8 or (detected and score >= 0.7):
        risk = "HIGH"
    elif score >= 0.45 or detected:
        risk = "MEDIUM"

    return {
        "detected": detected,
        "anomaly_score": round(score, 2),
        "risk_level": risk,
        "model": ml["model"] if ml else "statistical",
        "reasons": reasons[:6],
        "insufficient_data": False,
    }


def _isolation_forest(active_hours):
    if len(active_hours) < MIN_HOURS_FOR_ML:
        return None
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
    except Exception:
        return _zscore_fallback(active_hours)

    matrix = np.array([
        [
            row["requests"],
            row["failure_rate"],
            row["success_rate"],
            row["too_many_attempts"],
            row["failed"] + row["invalid"],
        ]
        for row in active_hours
    ], dtype=float)
    model = IsolationForest(
        n_estimators=80,
        contamination=0.12,
        random_state=42,
    )
    preds = model.fit_predict(matrix)
    raw = model.decision_function(matrix)
    latest = preds[-1]
    latest_score = float(raw[-1])
    anomaly_score = _normalize(-latest_score, -0.05, 0.25)
    reasons = []
    if latest == -1:
        last = active_hours[-1]
        reasons.append(
            f"IsolationForest flagged the last hour (requests={last['requests']}, failure_rate={last['failure_rate']}%)."
        )
    return {
        "detected": latest == -1,
        "anomaly_score": anomaly_score,
        "model": "IsolationForest",
        "reasons": reasons,
    }


def _zscore_fallback(active_hours):
    rates = [row["failure_rate"] for row in active_hours[:-1]]
    if len(rates) < 4:
        return None
    mean = sum(rates) / len(rates)
    var = sum((x - mean) ** 2 for x in rates) / len(rates)
    std = var ** 0.5
    last = active_hours[-1]["failure_rate"]
    z = 0 if std < 0.01 else abs(last - mean) / std
    detected = z >= 2.2
    return {
        "detected": detected,
        "anomaly_score": round(min(1.0, z / 4), 2),
        "model": "zscore",
        "reasons": [f"Last-hour failure rate {last}% vs mean {round(mean, 1)}% (z={round(z, 2)})."] if detected else [],
    }
