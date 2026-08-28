from ai.config import MIN_EVENTS_FOR_PREDICT


def predict_metrics(features):
    hourly = [row for row in (features.get("hourly") or []) if row["requests"] > 0]
    channels = features.get("channels") or {}
    items = []
    for name in ("sms", "whatsapp", "voice", "email"):
        items.append(_predict_channel(name, hourly, channels.get(name) or {}))
    volume = _predict_series(
        [row["requests"] for row in features.get("hourly") or []],
        label="request_volume",
        current=(features.get("totals") or {}).get("requests_last_hour", 0),
        unit="req/h",
    )
    return {
        "insufficient_data": bool(features.get("insufficient_data")),
        "items": items,
        "volume": volume,
    }


def _predict_channel(name, hourly, current):
    current_fail = current.get("failure_rate", 0)
    pred = current_fail
    risk = "LOW"
    if pred >= 20:
        risk = "HIGH"
    elif pred >= 12:
        risk = "MEDIUM"
    return {
        "channel": name,
        "metric": "failure_rate",
        "current": current_fail,
        "predicted": pred,
        "failure_rate": pred,
        "rate": pred,
        "risk": risk,
        "level": risk,
        "insufficient_data": current.get("requests", 0) == 0,
        "message": None,
    }


def _predict_series(values, label, current, unit):
    pred = _linear_next(values)
    if pred is None:
        pred = float(current or 0)
        thin = True
    else:
        thin = False
    return {
        "metric": label,
        "current": current,
        "predicted": pred,
        "unit": unit,
        "insufficient_data": thin,
        "message": None,
    }


def _linear_next(values):
    cleaned = [float(v) for v in values if v is not None]
    if len(cleaned) < MIN_EVENTS_FOR_PREDICT:
        return None
    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression
        x = np.arange(len(cleaned)).reshape(-1, 1)
        y = np.array(cleaned, dtype=float)
        model = LinearRegression()
        model.fit(x, y)
        nxt = float(model.predict([[len(cleaned)]])[0])
        return round(max(0.0, nxt), 1)
    except Exception:
        window = cleaned[-4:]
        delta = window[-1] - window[0]
        nxt = window[-1] + delta / max(len(window) - 1, 1)
        return round(max(0.0, nxt), 1)
