from pathlib import Path
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect
from flask_cors import CORS
from flask_limiter.errors import RateLimitExceeded

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from ai.jobs import start_ai_worker
from db import init_db
from otp.security import limiter
from product_config import CORS_ORIGINS, FLASK_DEBUG, FLASK_SECRET_KEY
from routes.admin import admin_bp
from routes.ai import ai_bp
from routes.auth import auth_bp
from routes.auth_extra import extra_bp
from routes.v1 import v1_bp

app = Flask(__name__)
if not FLASK_SECRET_KEY or not os.getenv("ADMIN_API_KEY"):
    raise RuntimeError("backend/.env incomplet : FLASK_SECRET_KEY et ADMIN_API_KEY sont requis")
app.secret_key = FLASK_SECRET_KEY
CORS(
    app,
    origins="*" if CORS_ORIGINS == ["*"] else CORS_ORIGINS,
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key", "X-Api-Key"],
)
limiter.init_app(app)
init_db()
app.register_blueprint(auth_bp)
app.register_blueprint(extra_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(v1_bp)
start_ai_worker()


@app.route("/")
def home():
    return redirect("/v1/docs")


@app.errorhandler(RateLimitExceeded)
def _ratelimit_handler(_e):
    return jsonify({
        "status": "error",
        "detail": "Trop de tentatives, réessayez plus tard",
    }), 429


if __name__ == "__main__":
    if not FLASK_SECRET_KEY or not os.getenv("ADMIN_API_KEY"):
        raise SystemExit("FLASK_SECRET_KEY et ADMIN_API_KEY sont requis dans backend/.env")
    if FLASK_DEBUG:
        print("ATTENTION: FLASK_DEBUG=1 — ne pas exposer ce processus sur Internet.")
    app.run(debug=FLASK_DEBUG, port=5000, host="127.0.0.1")
