# app/config.py
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi.middleware.cors import CORSMiddleware

# ---------- Allgemeine Konfiguration / ENV ----------
PRINT_WIDTH_PX = int(os.getenv("PRINT_WIDTH_PX", "576"))

PRINT_TOPIC = os.getenv("PRINT_TOPIC", "print/tickets")
PRINT_QOS = int(os.getenv("PRINT_QOS", "2"))

SETTINGS_FILE = os.getenv("SETTINGS_FILE", "settings.json")

GUEST_DB_FILE = os.getenv("GUEST_DB_FILE", "guest_tokens.json")

TIMEZONE = os.getenv("TIMEZONE", "Europe/Zurich")
TZ = ZoneInfo(TIMEZONE)


def now_str(fmt: str = "%d.%m.%Y %H:%M") -> str:
    return datetime.now(TZ).strftime(fmt)


def setup_cors(app):
    """CORS-Middleware zentral aktivieren."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
