import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "YouTube İndirici"
VERSION = "0.1.0"
AUTHOR = "Miraç Deprem"
REPOSITORY_URL = "https://github.com/MrcDprm/youtube-downloader"

# Windows'ta ffmpeg her çalıştığında siyah bir konsol penceresi açılmasın
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def resource_path(relative_path):
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return str(base_path / relative_path)


def find_tool(name):
    """Kurulumla gelen ffmpeg/ffprobe'u, yoksa (geliştirirken) PATH'teki kopyasını bulur."""
    bundled = Path(resource_path("vendor")) / f"{name}.exe"
    if bundled.is_file():
        return str(bundled)
    return shutil.which(name)
