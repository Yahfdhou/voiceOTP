import env_load  # noqa: F401
import os

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()
