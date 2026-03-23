# ora/config.py
# Config persistence: load/save the JSON config file.
# All modules that need persistent settings call load()/save() here.
# The config dict is a plain Python dict — no special classes needed.

import json
from .constants import CONFIG_FILE, DEFAULT_SPEED, DEFAULT_LANG, DEFAULT_CACHE_MAX_MB

DEFAULT_CONFIG: dict = {
    "lang": DEFAULT_LANG,
    "voice": "",
    "speed": DEFAULT_SPEED,
    "text": "",
    "cache_max_mb": DEFAULT_CACHE_MAX_MB,
    "clipboard_enabled": False,
    "clipboard_autostart": False,
}


def load() -> dict:
    """Load config from disk. Returns defaults for any missing keys."""
    try:
        data = json.loads(CONFIG_FILE.read_text())
        # Fill in any keys missing from the stored config (e.g. after upgrade)
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(data)
        return cfg
    except Exception:
        return dict(DEFAULT_CONFIG)


def save(cfg: dict) -> None:
    """Persist config dict to disk."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    except Exception as e:
        import sys
        print(f"[ora] warning: could not save config: {e}", file=sys.stderr)
