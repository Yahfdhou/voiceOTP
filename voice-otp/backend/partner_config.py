# Clés partenaires — une par client acheteur.
# Header : X-Api-Key: <clé>
# Révoquer = supprimer la ligne, puis redémarrer Flask.

PARTNER_KEYS = {
    "sk_live_demo_voiceotp_7f3a9c": {
        "name": "Compte démo (prof / tests)",
        "plan": "starter",
        "channels": ["voice", "sms", "whatsapp", "email"],
    },
    "sk_live_starter_4c91e2b8a7d05f33": {
        "name": "Client Starter 1",
        "plan": "starter",
        "channels": ["sms", "whatsapp", "email"],
    },
    "sk_live_starter_9e18a0c4d2b76f11": {
        "name": "Client Starter 2",
        "plan": "starter",
        "channels": ["sms", "whatsapp", "email"],
    },
    "sk_live_pro_b7f3c1a90e24d658": {
        "name": "Client Pro (3 canaux)",
        "plan": "pro",
        "channels": ["voice", "sms", "whatsapp", "email"],
    },
    "sk_live_pro_e5a82d17c9b0436f": {
        "name": "Client Pro 2",
        "plan": "pro",
        "channels": ["voice", "sms", "whatsapp", "email"],
    },
    "sk_live_bank_1d8c6e4a92f0b357": {
        "name": "Banque / paiement",
        "plan": "business",
        "channels": ["voice", "sms", "whatsapp", "email"],
    },
}

PRODUCT_NAME = "VoiceOTP Gateway"
PRODUCT_BASE = "http://127.0.0.1:5000"
VOICE_LOCAL_EXT = "1000"
