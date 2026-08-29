# Clés partenaires de démo — DÉSACTIVÉES par défaut.
# Ne jamais committer de vraies clés. Les comptes se créent via le dashboard admin.
# Pour un labo local uniquement : ENABLE_DEMO_KEYS=1 dans .env

import os

PARTNER_KEYS = {}

if os.getenv("ENABLE_DEMO_KEYS", "0").strip().lower() in ("1", "true", "yes"):
    PARTNER_KEYS = {
        "sk_live_demo_voiceotp_7f3a9c": {
            "name": "Compte démo (labo local)",
            "plan": "starter",
            "channels": ["voice", "sms", "whatsapp", "email"],
        },
    }

PRODUCT_NAME = "VoiceOTP Gateway"
PRODUCT_BASE = os.getenv("PRODUCT_BASE", "http://127.0.0.1:5000").rstrip("/")
VOICE_LOCAL_EXT = os.getenv("VOICE_LOCAL_EXT", "1000")
