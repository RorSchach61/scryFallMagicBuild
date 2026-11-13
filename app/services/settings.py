import json

from app.config import SETTINGS_PATH

DEFAULTS = {"dark_mode": False}

def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            saved = json.load(f)
    except(OSError,json.JSONDecodeError):
        return dict(DEFAULTS)
    if not isinstance(saved, dict):
        return dict(DEFAULTS)
    return {**DEFAULTS, **saved}

def save_settings(settings):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
