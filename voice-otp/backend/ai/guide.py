from ai.jobs import get_control_center


def _fr_num(value, digits=1):
    if value is None:
        return "non disponible"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number - round(number)) < 0.05:
        return str(int(round(number)))
    text = f"{number:.{digits}f}".replace(".", ",")
    return text


def _label_fr(label):
    mapping = {
        "Excellent": "excellente",
        "Good": "bonne",
        "Warning": "en alerte",
        "Critical": "critique",
        "HIGH": "élevé",
        "MEDIUM": "moyen",
        "LOW": "faible",
        "sms": "SMS",
        "whatsapp": "WhatsApp",
        "voice": "voix",
        "email": "e-mail",
    }
    return mapping.get(label, (label or "").lower())


def _duration(script):
    words = len((script or "").split())
    return max(8, round(words / 2.2))


def _item(section_id, title, route, script, hint=""):
    return {
        "id": section_id,
        "title": title,
        "route": route,
        "hint": hint,
        "language": "fr-FR",
        "script": script.strip(),
        "audio": f"/admin/ai/guide/audio?section={section_id}",
        "duration_hint_seconds": _duration(script),
    }


def build_guide(payload=None):
    data = payload or get_control_center()
    health = data.get("health") or {}
    kpis = data.get("kpis") or {}
    summary = data.get("daily_summary") or {}
    insights = data.get("insights") or {}
    llm = data.get("llm") or {}
    anomaly = data.get("anomaly") or {}
    channels = {row.get("channel"): row for row in (data.get("channels") or [])}
    sms = channels.get("sms") or {}
    whatsapp = channels.get("whatsapp") or {}
    voice = channels.get("voice") or {}
    email = channels.get("email") or {}
    recs = data.get("recommendations") or []
    rec_text = recs[0]["text"] if recs and isinstance(recs[0], dict) else ""
    system = data.get("system") or {}
    redis_ok = "connecté" if system.get("redis") else "hors ligne"
    provider = data.get("provider") or llm.get("provider") or "template"
    model = llm.get("model") or "llama3.2:3b"
    score = _fr_num(health.get("score"))
    success = _fr_num(kpis.get("success_rate"))
    failure = _fr_num(kpis.get("failure_rate"))
    sends = _fr_num(kpis.get("total_sends"), 0)
    anomaly_score = _fr_num(kpis.get("anomaly_score") or anomaly.get("anomaly_score"), 2)

    intro = _item(
        "intro",
        "Bienvenue",
        None,
        (
            "Bonjour. Je suis le guide vocal de la console OTP AI. "
            "Je vais vous expliquer, simplement, ce que vous voyez à l’écran, "
            "comme si nous faisions le tour ensemble. "
            "À gauche se trouve le menu. En haut, le titre de la page, le bouton Actualiser, "
            "et l’export. En bas à gauche, l’état du système : Redis, la base de données, et l’uptime. "
            "Les codes OTP et les numéros complets ne sont jamais lus à voix haute."
        ),
        "Accueil du guide",
    )
    sidebar = _item(
        "sidebar",
        "Menu latéral",
        None,
        (
            "Le menu de gauche contient les pages du produit. "
            "Tableau de bord : l’aperçu général OTP. "
            "Comptes : créer, modifier, désactiver les sociétés et leurs clés. "
            "Formule APIs : le contrat des quatre endpoints. "
            "Widget : tester les trois canaux comme un système externe. "
            "Journaux : l’historique. AI Control Center : l’analyse. "
            "Outils : Redis, un OTP de test, et le nettoyage. "
            "Cliquez sur un élément, puis sur Écouter : je vous explique cette page."
        ),
        "Navigation",
    )
    home = _item(
        "home",
        "Tableau de bord",
        "/",
        (
            "Vous êtes sur le Tableau de bord, l’accueil de l’administration. "
            "Cette page montre les indicateurs des 7, 14 ou 30 derniers jours : "
            "nombre de demandes, taux de succès, répartition par canal voix, SMS et e-mail, "
            "les statuts envoyé, vérifié, échoué, et un graphique d’évolution. "
            "Plus bas, vous voyez l’entonnoir, la carte de chaleur, les utilisateurs les plus actifs, "
            "et les dernières requêtes, avec la destination masquée. "
            "Servez-vous de cette page pour une vue d’ensemble. "
            "Pour comprendre pourquoi un taux baisse, ouvrez ensuite AI Control Center."
        ),
        "Aperçu général & AI",
    )
    logs = _item(
        "logs",
        "Journaux",
        "/logs",
        (
            "La page Journaux est l’historique. Chaque ligne est un événement : "
            "un envoi, une vérification réussie, un code invalide, une expiration, "
            "ou trop de tentatives. "
            "Vous pouvez filtrer par canal, par statut, et par dates, puis changer de page. "
            "Les destinations restent masquées, par sécurité. "
            "Utilisez cette page pour enquêter sur un incident précis, pas pour les tendances globales."
        ),
        "Historique des OTP",
    )
    ai = _item(
        "ai",
        "AI Control Center",
        "/ai",
        (
            f"Voici le AI Control Center, le cœur de l’analyse. "
            f"Aujourd’hui, la santé du système est de {score} sur 100, donc {_label_fr(health.get('label'))}. "
            f"Le taux de succès OTP est de {success} pour cent, le taux d’échec de {failure} pour cent, "
            f"pour un total de {sends} envois sur 24 heures. "
            f"Le score d’anomalie est de {anomaly_score} sur 1, risque {_label_fr(kpis.get('anomaly_risk') or anomaly.get('risk_level'))}. "
            f"Le modèle statistique IsolationForest surveille les écarts. "
            f"Le texte d’analyse peut être rédigé par Ollama, modèle {model}, "
            f"actuellement {'en ligne' if provider == 'ollama' else 'en secours automatique'}. "
            "Les cartes du bas détaillent les anomalies, les prédictions, les recommandations, "
            "le résumé du jour, et le copilote en bas de page. "
            "Rien ici ne déclenche d’action automatique : ce sont des conseils."
        ),
        "Analyses & recommandations",
    )
    tools = _item(
        "tools",
        "Outils",
        "/tools",
        (
            "La page Outils est réservée aux opérations. "
            "Vous y voyez l’état de Redis : les clés OTP temporaires, avec une durée de vie de 180 secondes. "
            "Vous pouvez envoyer un OTP de test vers la voix, le SMS ou l’e-mail. "
            "Attention : vider Redis supprime les codes encore valides. "
            "Le nettoyage efface les vieux événements SQLite de plus de 30 jours. "
            "Ces boutons sont destructeurs : confirmez toujours avant de cliquer."
        ),
        "Redis, test OTP, cleanup",
    )
    system = _item(
        "system",
        "Bloc Système",
        None,
        (
            f"En bas du menu, le bloc Système. Redis est {redis_ok}. "
            f"La base de données SQLite est {system.get('database') or 'OK'}. "
            "L’uptime affiché ici est indicatif. "
            "Si Redis est hors ligne, les OTP peuvent tomber en mémoire locale : surveillez ce voyant."
        ),
        "Redis, base, uptime",
    )
    kpis_section = _item(
        "kpis",
        "Indicateurs du haut",
        "/ai",
        (
            f"Les cinq cartes du haut résument les dernières 24 heures. "
            f"Santé du système : {score} sur 100, {_label_fr(health.get('label'))}. "
            f"Taux de succès : {success} pour cent. Taux d’échec : {failure} pour cent. "
            f"Total des envois : {sends}. "
            f"Anomaly Score : {anomaly_score} sur 1, {_label_fr(kpis.get('anomaly_risk'))}. "
            "La petite courbe sous chaque carte montre la tendance horaire. "
            "Si une valeur est un tiret, les données manquent encore."
        ),
    )
    channels_section = _item(
        "channels",
        "Performance par canal",
        "/ai",
        (
            f"Le tableau Performance par canal compare SMS, WhatsApp, voix et e-mail. "
            f"SMS : {_fr_num(sms.get('sent'), 0)} envois, {_fr_num(sms.get('success'), 0)} succès, "
            f"{_fr_num(sms.get('failed'), 0)} échecs, soit {_fr_num(sms.get('success_rate'))} pour cent de succès. "
            f"WhatsApp : {_fr_num(whatsapp.get('sent'), 0)} envois, {_fr_num(whatsapp.get('success'), 0)} succès. "
            f"Voix : {_fr_num(voice.get('sent'), 0)} envois, {_fr_num(voice.get('success'), 0)} succès. "
            f"E-mail : {_fr_num(email.get('sent'), 0)} envois, {_fr_num(email.get('success'), 0)} succès. "
            f"Le canal le plus fiable en ce moment est {_label_fr(summary.get('best_channel') or 'voice')}. "
            "La sparkline à droite montre si le volume monte ou descend."
        ),
    )
    timeseries = _item(
        "timeseries",
        "Évolution des envois",
        "/ai",
        (
            "Le graphique du milieu montre l’évolution des envois et des succès sur la période affichée. "
            "La courbe bleue, ce sont les envois. La verte, les vérifications réussies. "
            "Si les deux se séparent, trop de codes partent sans être validés. "
            "C’est souvent un problème SMS, un délai vocal, ou des tentatives invalides."
        ),
    )
    alerts = _item(
        "alerts",
        "Alertes intelligentes",
        "/ai",
        (
            "À droite, les alertes intelligentes. "
            "Elles apparaissent quand l’IA détecte une anomalie, par exemple un taux trop_many_attempts élevé, "
            "ou une prévision d’échec SMS. "
            "Ce n’est pas un journal brut : ce sont des signaux à traiter en priorité. "
            "Si la liste est vide, aucun écart majeur n’a été retenu."
        ),
    )
    insights = _item(
        "insights",
        "Analyse IA du jour",
        "/ai",
        (
            f"La carte Analyse IA du jour. "
            f"L’IA a détecté {_fr_num(insights.get('anomalies_count'), 0)} anomalie, "
            f"niveau de risque {_label_fr(insights.get('risk_level'))}, "
            f"confiance {_fr_num(insights.get('confidence'), 0)} pour cent. "
            f"{(insights.get('message') or 'Le détail textuel s’affiche après un Actualiser si Ollama est disponible.')} "
        ),
    )
    predictions = _item(
        "predictions",
        "Prédictions IA",
        "/ai",
        (
            "Les prédictions IA estiment le taux d’échec pour les prochaines heures, canal par canal. "
            "HIGH signifie : surveillez ce canal avant d’augmenter le trafic. "
            "LOW signifie : le canal est calme. "
            "Ce n’est pas une garantie, c’est une tendance calculée sur l’historique récent."
        ),
    )
    recommendations = _item(
        "recommendations",
        "Recommandations IA",
        "/ai",
        (
            "Les recommandations sont des conseils. Aucun bouton ici ne change Redis, ni les limites, ni les canaux. "
            f"{('Conseil actuel : ' + rec_text) if rec_text else 'Aucun conseil critique pour le moment.'} "
            "Un administrateur doit toujours valider avant d’agir."
        ),
    )
    daily = _item(
        "summary",
        "Résumé quotidien",
        "/ai",
        (
            f"Le résumé quotidien reprend les 24 dernières heures. "
            f"Total des envois : {_fr_num(summary.get('total_sends'), 0)}. "
            f"Vérifications réussies : {_fr_num(summary.get('verified'), 0)}. "
            f"Taux de succès : {_fr_num(summary.get('success_rate'))} pour cent. "
            f"Problème principal : {summary.get('main_issue') or 'aucun point bloquant nommé'}. "
            f"Risque {_label_fr(summary.get('risk_level'))}. "
            f"Canal le plus fiable : {_label_fr(summary.get('best_channel') or 'voix')}."
        ),
    )
    copilot = _item(
        "copilot",
        "AI Copilot",
        "/ai",
        (
            "En bas, le copilote. Posez une question en français, par exemple : "
            "pourquoi le taux d’échec SMS a-t-il augmenté, ou quel canal est le plus fiable. "
            "Il répond uniquement à partir des métriques agrégées. "
            "Il ne reçoit jamais le code OTP, le mot de passe, ni le numéro complet. "
            "Si Ollama est allumé, la réponse est rédigée par le modèle local. "
            "Sinon, un modèle de phrases utilise les mêmes chiffres."
        ),
    )

    accounts = _item(
        "accounts",
        "Comptes partenaires",
        "/accounts",
        (
            "Vous êtes sur la page Comptes. C’est ici que vous gérez les sociétés qui appellent le Web Service. "
            "En haut, les graphiques montrent les plans, les comptes actifs, et le quota du jour. "
            "Le formulaire sert à créer un nouveau compte : nom, e-mail, et plan. "
            "La clé API n’apparaît qu’une seule fois : copiez-la et envoyez le PDF à cette société uniquement. "
            "Dans le tableau, le champ de recherche filtre les comptes. "
            "Détail ouvre la fiche au centre. Modifier change le nom, l’e-mail ou le plan. "
            "Désactiver coupe l’accès immédiatement. Stats montre le volume de cette société. "
            "Le bouton Clé régénère une nouvelle clé et invalide l’ancienne."
        ),
        "Partenaires, clés, quotas",
    )
    account_detail = _item(
        "account-detail",
        "Fiche d’une société",
        None,
        (
            "Vous êtes sur la fiche statistiques d’une société. "
            "Cette page montre uniquement les demandes OTP de ce partenaire : "
            "total, dernières 24 heures, taux de succès, canaux, et les derniers événements. "
            "Vous pouvez régénérer la clé, désactiver ou réactiver le compte, et télécharger son PDF. "
            "Le bouton Retour ramène à la liste des comptes."
        ),
        "Statistiques d’un partenaire",
    )
    integration = _item(
        "integration",
        "Formule APIs",
        "/integration",
        (
            "Vous êtes sur Formule APIs. "
            "Cette page est le contrat d’intégration : les quatre appels HTTP pour les systèmes externes. "
            "Voix, SMS, e-mail, et un seul verify. "
            "Le partenaire n’installe rien : il envoie X-Api-Key et du JSON. "
            "Les erreurs 401, 403, 429 et 502 sont expliquées ici."
        ),
        "Contrat d’intégration",
    )
    widget = _item(
        "widget",
        "Widget de test",
        "/widget",
        (
            "Vous êtes sur Widget. "
            "Cette page simule un système externe : vous collez une clé partenaire, "
            "puis vous testez la voix, le SMS, l’e-mail, et la vérification. "
            "Cela prouve que le Web Service fonctionne tout seul. "
            "Utilisez uniquement la clé d’un compte partenaire, jamais la clé admin."
        ),
        "Test des 3 canaux",
    )

    playlist = [
        intro, sidebar, home, accounts, account_detail, integration, widget,
        logs, ai, tools, system,
        kpis_section, channels_section, timeseries, alerts,
        insights, predictions, recommendations, daily, copilot,
    ]
    by_id = {item["id"]: item for item in playlist}
    full_script = " ".join(item["script"] for item in [
        intro, sidebar, home, accounts, integration, widget, logs, ai, tools, system
    ])
    by_id["full"] = _item(
        "full",
        "Visite guidée complète",
        None,
        full_script,
        "Tout le menu, d’une traite",
    )
    by_id["ai-page"] = _item(
        "ai-page",
        "Page AI Control Center, détail",
        "/ai",
        " ".join(item["script"] for item in [
            ai, kpis_section, channels_section, timeseries, alerts,
            insights, predictions, recommendations, daily, copilot,
        ]),
        "Tous les blocs de la page AI",
    )
    order = [
        "intro", "sidebar", "home", "accounts", "account-detail",
        "integration", "widget", "logs", "ai", "tools", "system",
        "kpis", "channels", "timeseries", "alerts", "insights",
        "predictions", "recommendations", "summary", "copilot",
        "ai-page", "full",
    ]
    return {
        "language": "fr-FR",
        "voice": "Windows SAPI, voix française si installée (Hortense / fr-FR)",
        "generated_at": data.get("generated_at"),
        "mic": {
            "label": "Écouter le guide",
            "hint": "Au clic, jouer playlist dans l’ordre, ou un seul section id.",
            "default_section": "full",
            "page_section": {
                "/": "home",
                "/accounts": "accounts",
                "/integration": "integration",
                "/widget": "widget",
                "/logs": "logs",
                "/ai": "ai-page",
                "/tools": "tools",
            },
        },
        "playlist": [by_id[key] for key in order],
        "sections": by_id,
    }


def get_section(section_id, payload=None):
    guide = build_guide(payload)
    key = (section_id or "full").strip().lower()
    item = guide["sections"].get(key)
    if not item:
        return None, guide
    return item, guide
