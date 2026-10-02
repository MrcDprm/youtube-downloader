import json
import os
from pathlib import Path

DATA_DIR = Path.home() / ".youtube-downloader"


def load_json(name, default):
    try:
        with open(DATA_DIR / name, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError, RecursionError):
        return default


def save_json(name, data):
    try:
        DATA_DIR.mkdir(exist_ok=True)
        temp_path = DATA_DIR / f"{name}.tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, DATA_DIR / name)
    except OSError:
        pass
