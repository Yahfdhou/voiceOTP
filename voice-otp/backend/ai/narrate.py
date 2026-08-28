from ai.providers import ask_llm, ollama_status


COPILOT_SYSTEM = (
    "You are the Voice OTP admin copilot. Answer only from CONTEXT JSON. "
    "Never invent statistics. Never ask for or reveal OTP codes, passwords, "
    "API keys, or full phone numbers. Write in French, 3-6 sentences. "
    "Termine toujours tes phrases. Ne t'arrête jamais au milieu d'une phrase. "
    "If the context cannot answer, reply exactly: "
    "Les données disponibles sont insuffisantes pour répondre avec certitude."
)


def _compact_context(context):
    ctx = context or {}
    return {
        "period": ctx.get("period"),
        "totals": ctx.get("totals"),
        "sms": ctx.get("sms"),
        "whatsapp": ctx.get("whatsapp"),
        "voice": ctx.get("voice"),
        "email": ctx.get("email"),
        "health": ctx.get("health"),
        "anomaly": ctx.get("anomaly"),
        "predictions": ctx.get("predictions"),
    }


def _facts(context):
    ctx = _compact_context(context)
    totals = ctx.get("totals") or {}
    health = ctx.get("health") or {}
    sms = ctx.get("sms") or {}
    whatsapp = ctx.get("whatsapp") or {}
    voice = ctx.get("voice") or {}
    email = ctx.get("email") or {}
    anomaly = ctx.get("anomaly") or {}
    reasons = "; ".join(anomaly.get("reasons") or [])
    return (
        f"Santé {health.get('score')}/100 ({health.get('label')}), "
        f"risque {health.get('risk_level') or anomaly.get('risk_level')}. "
        f"Envois 24h: {totals.get('requests')}, succès {totals.get('success_rate')}%, "
        f"échec {totals.get('failure_rate')}%, too_many_attempts {totals.get('too_many_attempts_rate')}%. "
        f"SMS: {sms.get('requests')} req, échec {sms.get('failure_rate')}%, fiabilité {sms.get('reliability')}%. "
        f"WhatsApp: {whatsapp.get('requests')} req, échec {whatsapp.get('failure_rate')}%, fiabilité {whatsapp.get('reliability')}%. "
        f"Voice: {voice.get('requests')} req, échec {voice.get('failure_rate')}%, fiabilité {voice.get('reliability')}%. "
        f"Email: {email.get('requests')} req, échec {email.get('failure_rate')}%, fiabilité {email.get('reliability')}%. "
        f"Modèle anomalie: {anomaly.get('model')}, score {anomaly.get('anomaly_score')}. "
        f"Raisons: {reasons or 'aucune'}."
    )


def _strip_label(text, labels):
    value = (text or "").strip().lstrip("*").strip()
    lower = value.lower()
    for label in labels:
        prefix = f"{label} :"
        prefix2 = f"{label}:"
        if lower.startswith(prefix):
            return value[len(prefix):].strip().lstrip("*").strip()
        if lower.startswith(prefix2):
            return value[len(prefix2):].strip().lstrip("*").strip()
    return value


def generate_dashboard_narrative(context):
    status = ollama_status()
    facts = _facts(context)
    analysis, provider, model = ask_llm(
        "Tu es un analyste OTP. Écris en français uniquement. N'invente aucun chiffre. "
        "Termine toujours tes phrases. Ne t'arrête jamais au milieu d'une phrase.",
        (
            "Rédige un titre court puis 4 phrases d'analyse. "
            "Première ligne = titre. Ensuite le paragraphe. "
            "Utilise uniquement ces faits:\n"
            + facts
        ),
        {"facts": facts},
        json_mode=False,
    )
    if provider != "ollama" or not analysis or len(analysis) < 40:
        return None, provider, model, status
    lines = [line.strip() for line in analysis.splitlines() if line.strip()]
    headline = lines[0][:120] if lines else "Analyse IA de la plateforme OTP"
    headline = _strip_label(headline, ("titre", "headline", "title"))
    body = " ".join(lines[1:] if len(lines) > 1 else lines)
    body = _strip_label(body, ("analyse", "analysis"))
    if len(body) < 40:
        body = analysis.strip()
        headline = "Analyse IA de la plateforme OTP"
    rec_text, rec_provider, _ = ask_llm(
        "Tu es un analyste OTP. Réponds en français. N'invente aucun chiffre. Aucune action automatique. "
        "Termine toujours tes phrases. Ne t'arrête jamais au milieu d'une phrase.",
        "Donne 3 conseils opérationnels, un par ligne, chacun commençant par '- '.\nFaits:\n" + facts,
        {"facts": facts},
        json_mode=False,
    )
    recs = []
    if rec_provider == "ollama" and rec_text:
        for line in rec_text.splitlines():
            item = line.strip().lstrip("-•* ").strip()
            if len(item) >= 12:
                recs.append(item)
    issue, _, _ = ask_llm(
        "Réponds par une courte phrase française uniquement. "
        "Termine toujours tes phrases. Ne t'arrête jamais au milieu d'une phrase.",
        "Quel est le problème principal en une phrase?\n" + facts,
        {"facts": facts},
        json_mode=False,
    )
    return {
        "headline": headline,
        "analysis": body,
        "recommendations": recs[:5],
        "main_issue": (issue or "").strip()[:180] or None,
    }, provider, model, status


def generate_copilot_answer(question, context):
    facts = _facts(context)
    text, provider, model = ask_llm(
        COPILOT_SYSTEM,
        question + "\n\nFaits:\n" + facts,
        _compact_context(context),
    )
    return (text or "").strip(), provider, model
