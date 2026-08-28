# Charge backend/.env — jamais de mot de passe ici.
import os

import env_load  # noqa: F401

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").replace(" ", "").strip()
SMTP_FROM = (os.getenv("SMTP_FROM", "") or SMTP_USER).strip()
