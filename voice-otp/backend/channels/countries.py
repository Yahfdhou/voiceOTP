COUNTRIES = [
    {"iso": "MR", "name": "Mauritanie", "dial": "222", "minLen": 8, "maxLen": 8},
    {"iso": "MA", "name": "Maroc", "dial": "212", "minLen": 9, "maxLen": 9},
    {"iso": "SN", "name": "Sénégal", "dial": "221", "minLen": 9, "maxLen": 9},
    {"iso": "ML", "name": "Mali", "dial": "223", "minLen": 8, "maxLen": 8},
    {"iso": "GN", "name": "Guinée", "dial": "224", "minLen": 9, "maxLen": 9},
    {"iso": "CI", "name": "Côte d'Ivoire", "dial": "225", "minLen": 10, "maxLen": 10},
    {"iso": "BF", "name": "Burkina Faso", "dial": "226", "minLen": 8, "maxLen": 8},
    {"iso": "NE", "name": "Niger", "dial": "227", "minLen": 8, "maxLen": 8},
    {"iso": "TG", "name": "Togo", "dial": "228", "minLen": 8, "maxLen": 8},
    {"iso": "BJ", "name": "Bénin", "dial": "229", "minLen": 8, "maxLen": 8},
    {"iso": "DZ", "name": "Algérie", "dial": "213", "minLen": 9, "maxLen": 9},
    {"iso": "TN", "name": "Tunisie", "dial": "216", "minLen": 8, "maxLen": 8},
    {"iso": "LY", "name": "Libye", "dial": "218", "minLen": 9, "maxLen": 10},
    {"iso": "EG", "name": "Égypte", "dial": "20", "minLen": 10, "maxLen": 10},
    {"iso": "SA", "name": "Arabie saoudite", "dial": "966", "minLen": 9, "maxLen": 9},
    {"iso": "AE", "name": "Émirats", "dial": "971", "minLen": 9, "maxLen": 9},
    {"iso": "QA", "name": "Qatar", "dial": "974", "minLen": 8, "maxLen": 8},
    {"iso": "KW", "name": "Koweït", "dial": "965", "minLen": 8, "maxLen": 8},
    {"iso": "FR", "name": "France", "dial": "33", "minLen": 9, "maxLen": 9},
    {"iso": "ES", "name": "Espagne", "dial": "34", "minLen": 9, "maxLen": 9},
    {"iso": "BE", "name": "Belgique", "dial": "32", "minLen": 8, "maxLen": 9},
    {"iso": "DE", "name": "Allemagne", "dial": "49", "minLen": 10, "maxLen": 11},
    {"iso": "IT", "name": "Italie", "dial": "39", "minLen": 9, "maxLen": 10},
    {"iso": "GB", "name": "Royaume-Uni", "dial": "44", "minLen": 10, "maxLen": 10},
    {"iso": "US", "name": "États-Unis", "dial": "1", "minLen": 10, "maxLen": 10},
    {"iso": "CA", "name": "Canada", "dial": "1", "minLen": 10, "maxLen": 10},
    {"iso": "TR", "name": "Turquie", "dial": "90", "minLen": 10, "maxLen": 10},
]


def get_country(dial_or_iso):
    raw = str(dial_or_iso or "").strip().lstrip("+")
    for row in COUNTRIES:
        if row["dial"] == raw or row["iso"].lower() == raw.lower():
            return row
    return None
