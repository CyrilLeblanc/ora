# ora/constants.py
# Central place for paths, URLs, and immutable defaults.
# Imported by all other modules — never import from sibling modules here
# to keep the dependency graph acyclic.

from pathlib import Path

# ── Remote resources ──────────────────────────────────────────────────────────

VOICES_JSON_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/voices.json"
)
HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

# ── Local paths ───────────────────────────────────────────────────────────────

DATA_DIR   = Path.home() / ".local" / "share" / "ora"
MODELS_DIR = DATA_DIR / "models"
CACHE_DIR  = DATA_DIR / "cache"
CONFIG_FILE = DATA_DIR / "config.json"

# Ensure directories exist at import time (safe to call repeatedly)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Audio settings ────────────────────────────────────────────────────────────

APLAY_RATE = 22050     # sample rate expected by piper --output-raw
APLAY_FORMAT = "S16_LE"

# ── Application defaults ──────────────────────────────────────────────────────

DEFAULT_SPEED         = 1.0
DEFAULT_LANG          = "fr"
DEFAULT_CACHE_MAX_MB  = 200
CLIPBOARD_POLL_MS     = 500   # clipboard watcher interval in milliseconds
CHUNK_MIN_LEN         = 20    # minimum characters per TTS chunk

# ── Language name map (code → display name) ───────────────────────────────────

LANG_NAMES: dict[str, str] = {
    "fr": "Français",  "en": "English",    "de": "Deutsch",
    "es": "Español",   "it": "Italiano",   "pt": "Português",
    "nl": "Nederlands","pl": "Polski",      "ru": "Русский",
    "zh": "中文",      "ja": "日本語",     "ko": "한국어",
    "ar": "العربية",   "cs": "Čeština",    "da": "Dansk",
    "fi": "Suomi",     "hu": "Magyar",     "nb": "Norsk",
    "ro": "Română",    "sk": "Slovenčina", "sv": "Svenska",
    "tr": "Türkçe",    "uk": "Українська", "vi": "Tiếng Việt",
    "ca": "Català",    "el": "Ελληνικά",   "fa": "فارسی",
    "is": "Íslenska",  "ka": "ქართული",    "lb": "Lëtzebuergesch",
    "ne": "नेपाली",   "sr": "Српски",      "sw": "Kiswahili",
}

# ── GTK CSS ───────────────────────────────────────────────────────────────────

CSS = b"""
window { background-color: #242424; }
.title-bar { background-color: #1c1c1c; padding: 8px 12px; }
.title-label { color: #ffffff; font-weight: bold; font-size: 15px; }
textview, textview text { background-color: #2e2e2e; color: #e0e0e0; font-size: 13px; }
.status-bar { background-color: #161616; padding: 4px 12px; }
.status-label { color: #888888; font-size: 11px; }
.voice-label { color: #aaaaaa; font-size: 11px; }
.btn-play    { background-color: #2d6a4f; color: white; border-radius: 6px; padding: 6px 16px; }
.btn-play:hover { background-color: #40916c; }
.btn-pause   { background-color: #5a4a1c; color: white; border-radius: 6px; padding: 6px 16px; }
.btn-pause:hover { background-color: #7a6a2c; }
.btn-stop    { background-color: #7b2d2d; color: white; border-radius: 6px; padding: 6px 16px; }
.btn-stop:hover { background-color: #a33a3a; }
.btn-secondary { background-color: #3a3a3a; color: #dddddd; border-radius: 6px; padding: 6px 12px; }
.btn-secondary:hover { background-color: #4a4a4a; }
.btn-settings { background-color: #2a2a2a; color: #cccccc; border-radius: 6px; padding: 4px 10px; font-size: 12px; }
.btn-settings:hover { background-color: #3a3a3a; }
.btn-icon { background-color: #3a3a3a; color: #dddddd; border-radius: 6px; padding: 6px 10px; }
.btn-icon:hover { background-color: #4a4a4a; }
.installed-badge { color: #52b788; font-size: 11px; font-weight: bold; }
combobox { background-color: #3a3a3a; color: #dddddd; }
scale trough { background-color: #3a3a3a; }
scale highlight { background-color: #40916c; }
.dl-progress trough { background-color: #2a2a2a; border-radius: 3px; min-height: 5px; }
.dl-progress progress { background-color: #2166a0; border-radius: 3px; min-height: 5px; }
.chunk-progress trough { background-color: #2a2a2a; border-radius: 3px; min-height: 6px; }
.chunk-progress progress { background-color: #2d6a4f; border-radius: 3px; min-height: 6px; }
.clipboard-dot-off { color: #666666; font-size: 14px; background: none; border: none; padding: 2px 6px; }
.clipboard-dot-on  { color: #52b788;  font-size: 14px; background: none; border: none; padding: 2px 6px; }
.speed-label { color: #aaaaaa; font-size: 11px; }
.control-row { background-color: #1e1e1e; padding: 8px 12px; }
.separator-line { background-color: #333333; }
dialog { background-color: #242424; }
dialog .section-title { color: #aaaaaa; font-size: 11px; font-weight: bold; margin-top: 8px; }
dialog label { color: #dddddd; }
dialog entry { background-color: #3a3a3a; color: #dddddd; border: 1px solid #555; }
.btn-danger { background-color: #5c2020; color: #ffaaaa; border-radius: 4px; padding: 4px 10px; font-size: 11px; }
.btn-danger:hover { background-color: #7b2d2d; }
"""
