import os, json
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import ImageFont

# ---- Globale App-Einstellungen ----
APP_API_KEY = os.getenv("API_KEY", "change_me")
MQTT_HOST   = os.getenv("MQTT_HOST")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USER   = os.getenv("MQTT_USERNAME")
MQTT_PASS   = os.getenv("MQTT_PASSWORD")
MQTT_TLS    = os.getenv("MQTT_TLS", "true").lower() == "true"
TOPIC       = os.getenv("PRINT_TOPIC", "print/tickets")
PUBLISH_QOS = int(os.getenv("PRINT_QOS", "2"))

UI_PASS = os.getenv("UI_PASS", "set_me")
COOKIE_NAME = "ui_token"
UI_REMEMBER_DAYS = int(os.getenv("UI_REMEMBER_DAYS", "30"))
TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Zurich"))

PRINT_WIDTH_PX = int(os.getenv("PRINT_WIDTH_PX", "576"))
SETTINGS_FILE  = os.getenv("SETTINGS_FILE", "settings.json")
GUEST_DB_FILE  = os.getenv("GUEST_DB_FILE", "guest_tokens.json")

def now_str(fmt="%d.%m.%Y %H:%M") -> str:
    return datetime.now(TZ).strftime(fmt)

# ---- settings.json + ENV overlay ----
def _load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _save_settings(data: dict):
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_FILE)

SETTINGS = _load_settings()

def cfg_get(name: str, default=None):
    if name in SETTINGS:
        return SETTINGS[name]
    return os.getenv(name, default)

def cfg_get_int(name: str, default: int) -> int:
    try: return int(cfg_get(name, default))
    except: return default

def cfg_get_float(name: str, default: float) -> float:
    try: return float(cfg_get(name, default))
    except: return default

def cfg_get_bool(name: str, default: bool) -> bool:
    v = str(cfg_get(name, default)).lower()
    return v in ("1","true","yes","on","y","t")

# ---- ReceiptCfg ----
class ReceiptCfg:
    def __init__(self):
        self.preset = str(cfg_get("RECEIPT_PRESET", "clean")).lower()

        self.title_size = 36
        self.text_size  = 28
        self.time_size  = 24

        self.title_font_name = cfg_get("RECEIPT_TITLE_FONT", "DejaVuSans.ttf")
        self.text_font_name  = cfg_get("RECEIPT_TEXT_FONT",  "DejaVuSans.ttf")
        self.time_font_name  = cfg_get("RECEIPT_TIME_FONT",  "DejaVuSans.ttf")

        self.margin_top    = 28
        self.margin_bottom = 18
        self.margin_left   = 18
        self.margin_right  = 18

        self.gap_title_text   = 10
        self.line_height_mult = 1.15

        self.align_title = cfg_get("RECEIPT_ALIGN_TITLE", "left")
        self.align_text  = cfg_get("RECEIPT_ALIGN_TEXT",  "left")
        self.align_time  = cfg_get("RECEIPT_ALIGN_TIME",  "left")

        self.time_show_minutes = cfg_get_bool("RECEIPT_TIME_SHOW_MINUTES", True)
        self.time_show_seconds = cfg_get_bool("RECEIPT_TIME_SHOW_SECONDS", False)
        self.time_prefix       = cfg_get("RECEIPT_TIME_PREFIX", "")

        self.rule_after_title  = cfg_get_bool("RECEIPT_RULE_AFTER_TITLE", False)
        self.rule_px           = cfg_get_int("RECEIPT_RULE_PX", 1)
        self.rule_pad          = cfg_get_int("RECEIPT_RULE_PAD", 6)

        if self.preset == "compact":
            self.title_size, self.text_size, self.time_size = 30, 24, 22
            self.margin_top, self.margin_bottom = 16, 12
            self.gap_title_text = 6
            self.line_height_mult = 1.05
        elif self.preset == "bigtitle":
            self.title_size = 44
            self.gap_title_text = 14
            self.rule_after_title = True

        self.title_size = cfg_get_int("RECEIPT_TITLE_SIZE", self.title_size)
        self.text_size  = cfg_get_int("RECEIPT_TEXT_SIZE",  self.text_size)
        self.time_size  = cfg_get_int("RECEIPT_TIME_SIZE",  self.time_size)

        self.margin_top    = cfg_get_int("RECEIPT_MARGIN_TOP",    self.margin_top)
        self.margin_bottom = cfg_get_int("RECEIPT_MARGIN_BOTTOM", self.margin_bottom)
        self.margin_left   = cfg_get_int("RECEIPT_MARGIN_LEFT",   self.margin_left)
        self.margin_right  = cfg_get_int("RECEIPT_MARGIN_RIGHT",  self.margin_right)

        self.gap_title_text   = cfg_get_int("RECEIPT_GAP_TITLE_TEXT", self.gap_title_text)
        self.line_height_mult = cfg_get_float("RECEIPT_LINE_HEIGHT",   self.line_height_mult)

        self.font_title = _safe_font(self.title_font_name, self.title_size)
        self.font_text  = _safe_font(self.text_font_name,  self.text_size)
        self.font_time  = _safe_font(self.time_font_name,  self.time_size)

def _safe_font(path_or_name: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path_or_name, size=size)
    except:
        for cand in ("DejaVuSans.ttf", "Arial.ttf"):
            try: return ImageFont.truetype(cand, size=size)
            except: pass
    return ImageFont.load_default()

# --- CORS Setup --------------------------------------------------------------
from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app):
    """
    Hängt ein offenes CORS-Middleware an (für interne Tools/UI völlig ok).
    Wenn du Domains einschränken willst, passe allow_origins an.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],     # oder z.B. ["https://deine-domain.tld"]
        allow_methods=["*"],
        allow_headers=["*"],
    )
