"""Serveur production local. Gunicorn (Linux/AWS) ou Waitress (Windows)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)
os.chdir(ROOT)

HOST = os.getenv("BIND_HOST", "127.0.0.1")
PORT = os.getenv("BIND_PORT", "5000")
WORKERS = os.getenv("WEB_WORKERS", "2")


def main():
    if sys.platform == "win32":
        from waitress import serve
        from app import app

        print(f"Waitress (Windows) http://{HOST}:{PORT}  — Gunicorn sera utilisé sur AWS/Linux")
        serve(app, host=HOST, port=int(PORT), threads=max(int(WORKERS), 2))
        return

    os.execvp(
        "gunicorn",
        [
            "gunicorn",
            "-w",
            str(WORKERS),
            "-b",
            f"{HOST}:{PORT}",
            "app:app",
        ],
    )


if __name__ == "__main__":
    main()
