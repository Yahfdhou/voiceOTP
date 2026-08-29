from pathlib import Path
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect
from flask_cors import CORS
from flask_limiter.errors import RateLimitExceeded

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from ai.jobs import start_ai_worker
from db import init_db
from otp.generator import OTP_SECRET
from otp.security import limiter
from product_config import CORS_ORIGINS, FLASK_DEBUG, FLASK_SECRET_KEY
from routes.admin import admin_bp
from routes.ai import ai_bp
from routes.v1 import v1_bp

app = Flask(__name__)

if FLASK_DEBUG and os.getenv("ENV", "").strip().lower() in ("production", "prod"):
    raise RuntimeError("FLASK_DEBUG=1 interdit en production (ENV=production)")

if not FLASK_SECRET_KEY or not os.getenv("ADMIN_API_KEY"):
    raise RuntimeError("backend/.env incomplet : FLASK_SECRET_KEY et ADMIN_API_KEY sont requis")

otp_secret = (OTP_SECRET or os.getenv("OTP_SECRET", "")).strip()
if not otp_secret or otp_secret == "voice-otp-dev-change-me" or len(otp_secret) < 24:
    raise RuntimeError(
        "OTP_SECRET manquant ou trop faible (min. 24 caractères aléatoires). "
        "Ajoutez OTP_SECRET dans backend/.env"
    )

app.secret_key = FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # 16 KB — payloads OTP uniquement

_cors_origins = CORS_ORIGINS if CORS_ORIGINS else ["http://127.0.0.1:3000"]
CORS(
    app,
    origins="*" if _cors_origins == ["*"] else _cors_origins,
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key", "X-Api-Key"],
    supports_credentials=False,
)
limiter.init_app(app)
init_db()

# Routes legacy /auth/* désactivées par défaut (ouvertes = risque spam OTP).
# Activer seulement pour labo : ENABLE_LEGACY_AUTH=1
if os.getenv("ENABLE_LEGACY_AUTH", "0").strip() in ("1", "true", "yes"):
    from routes.auth import auth_bp
    from routes.auth_extra import extra_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(extra_bp)

app.register_blueprint(admin_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(v1_bp)
start_ai_worker()


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    )
    return response


@app.route("/")
def home():
    return redirect("/v1/docs")


@app.errorhandler(RateLimitExceeded)
def _ratelimit_handler(_e):
    return jsonify({
        "status": "error",
        "detail": "Trop de tentatives, réessayez plus tard",
    }), 429


@app.errorhandler(413)
def _too_large(_e):
    return jsonify({
        "status": "error",
        "detail": "payload_too_large",
    }), 413


if __name__ == "__main__":
    if not FLASK_SECRET_KEY or not os.getenv("ADMIN_API_KEY"):
        raise SystemExit("FLASK_SECRET_KEY et ADMIN_API_KEY sont requis dans backend/.env")
    if FLASK_DEBUG:
        print("ATTENTION: FLASK_DEBUG=1 — ne pas exposer ce processus sur Internet.")
    app.run(debug=FLASK_DEBUG, port=5000, host="127.0.0.1")
