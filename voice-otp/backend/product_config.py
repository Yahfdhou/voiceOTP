import env_load  # noqa: F401
import os

PRODUCT_NAME = os.getenv("PRODUCT_NAME", "VoiceOTP Gateway")
PRODUCT_BASE = os.getenv("PRODUCT_BASE", "http://127.0.0.1:5000")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip()
CORS_ORIGINS = [item.strip() for item in os.getenv("CORS_ORIGINS", "*").split(",") if item.strip()]
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0").strip() not in ("0", "false", "False")
VOICE_LOCAL_EXT = os.getenv("VOICE_LOCAL_EXT", "1000")
VOICE_PROVIDER = os.getenv("VOICE_PROVIDER", "lab").strip().lower()
SIP_TRUNK_NAME = os.getenv("SIP_TRUNK_NAME", "trunk").strip() or "trunk"
SIP_TRUNK_STRIP_PLUS = os.getenv("SIP_TRUNK_STRIP_PLUS", "1").strip() not in ("0", "false", "False")
SIP_TRUNK_CALLER_ID = os.getenv("SIP_TRUNK_CALLER_ID", "VoiceOTP").strip() or "VoiceOTP"


def voice_is_trunk():
    return VOICE_PROVIDER in ("trunk", "sip", "sip_trunk")


def voice_is_telnyx_cloud():
    """TeXML / Call Control : TTS chez Telnyx, pas de RTP vers le PC local."""
    return VOICE_PROVIDER in ("telnyx", "telnyx_api", "texml", "call_control")
