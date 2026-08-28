# ChinqIT Verify — https://docs.sms.chinqit.com/api-v2
# La clé se met uniquement dans backend/.env (CHINQIT_API_KEY).
import os

import env_load  # noqa: F401

CHINQIT_API_URL = os.getenv(
    "CHINQIT_API_URL",
    "https://sms.chinqit.com/api/v2/notify",
).strip()
CHINQIT_API_KEY = os.getenv("CHINQIT_API_KEY", "").strip()

_NOTIFY = CHINQIT_API_URL.rstrip("/")
if _NOTIFY.endswith("/notify"):
    _CHINQIT_V2 = _NOTIFY[: -len("/notify")]
else:
    _CHINQIT_V2 = "https://sms.chinqit.com/api/v2"

CHINQIT_CODE_URL = os.getenv(
    "CHINQIT_CODE_URL",
    f"{_CHINQIT_V2}/code",
).strip()
CHINQIT_CHECK_URL = os.getenv(
    "CHINQIT_CHECK_URL",
    f"{_CHINQIT_V2}/check",
).strip()
