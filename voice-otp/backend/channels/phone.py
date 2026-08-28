import re

from channels.countries import get_country

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def normalize_email(value):
    email = (value or "").strip().lower()
    if not EMAIL_RE.match(email):
        return None, "Adresse e-mail invalide."
    if email.endswith("@example.com") or email.endswith("@test.com"):
        return None, "Entrez votre vraie adresse e-mail."
    return email, None


def national_digits(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits.lstrip("0")
    return digits


def to_e164(country_code, national_number):
    country = get_country(country_code)
    if country is None:
        return None, "Indicatif pays invalide."

    digits = national_digits(national_number)
    if not digits:
        return None, "Numéro de téléphone requis."
    if len(digits) < country["minLen"] or len(digits) > country["maxLen"]:
        if country["minLen"] == country["maxLen"]:
            return None, f"Le numéro {country['name']} doit contenir {country['minLen']} chiffres."
        return None, (
            f"Le numéro {country['name']} doit contenir "
            f"{country['minLen']} à {country['maxLen']} chiffres."
        )

    return f"+{country['dial']}{digits}", None


def mask_email(email):
    local, _, domain = email.partition("@")
    if len(local) <= 1:
        hidden = "*"
    else:
        hidden = local[0] + "***"
    return f"{hidden}@{domain}"


def mask_phone(e164):
    digits = re.sub(r"\D", "", e164)
    if len(digits) <= 6:
        return "+" + ("*" * len(digits))
    prefix = digits[:-4]
    hidden = prefix[:3] + "****" if len(prefix) >= 3 else "****"
    return f"+{hidden}{digits[-4:]}"


def mask_destination(channel, dest):
    if channel == "email":
        return mask_email(dest)
    return mask_phone(dest)


def public_countries():
    return [
        {
            "iso": row["iso"],
            "name": row["name"],
            "dial": f"+{row['dial']}",
            "minLen": row["minLen"],
            "maxLen": row["maxLen"],
        }
        for row in COUNTRIES
    ]
