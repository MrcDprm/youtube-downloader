"""Kullanıcı ayarları: dil, tema, indirme formatı ve kayıt klasörü.

Dosyadan okunan değerlere güvenilmez; bilinmeyen ya da bozuk değer yerine varsayılan kullanılır.
"""
from formats import AUDIO_FORMATS, VIDEO_QUALITIES
from storage import load_json, save_json

SETTINGS_FILE = "settings.json"
LANGUAGES = ("tr", "en")
THEMES = ("dark", "light")
MAX_PATH_LENGTH = 500
# Format seçimi tek bir anahtar olarak saklanır: "video:1080p", "audio:mp3"
FORMAT_CHOICES = [f"video:{key}" for key in VIDEO_QUALITIES] + [f"audio:{key}" for key in AUDIO_FORMATS]


def default_settings():
    return {"lang": "tr", "theme": "dark", "format": "video:1080p", "output_dir": None}


def clean_settings(data):
    settings = default_settings()
    if not isinstance(data, dict):
        return settings
    for key, allowed in (("lang", LANGUAGES), ("theme", THEMES), ("format", FORMAT_CHOICES)):
        if data.get(key) in allowed:
            settings[key] = data[key]
    output_dir = data.get("output_dir")
    if isinstance(output_dir, str) and 0 < len(output_dir) <= MAX_PATH_LENGTH:
        settings["output_dir"] = output_dir
    return settings


def load_settings():
    return clean_settings(load_json(SETTINGS_FILE, None))


def save_settings(settings):
    save_json(SETTINGS_FILE, settings)
