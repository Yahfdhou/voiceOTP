# AI Control Center — independent from OTP generation.

OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_MODEL = "llama3.2:3b"
AI_REFRESH_SECONDS = 300
MIN_HOURS_FOR_ML = 3
MIN_EVENTS_FOR_PREDICT = 3
ASK_MAX_CHARS = 500
# Timeouts larges : EC2 t3.small en CPU peut être lent au 1er chargement du modèle
OLLAMA_TIMEOUT_ASK = 90
OLLAMA_TIMEOUT_DASHBOARD = 180
OLLAMA_NUM_PREDICT = 256
