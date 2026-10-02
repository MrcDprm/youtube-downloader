"""Kurulum dosyasına gömülecek FFmpeg'i vendor/ klasörüne indirir.

Sabit bir sürüm indirilir ve SHA-256 özeti kontrol edilir: dosya yolda değiştirilmişse kullanılmaz.
Derlemeden önce bir kez çalıştırılır:  python scripts/fetch_ffmpeg.py
"""
import hashlib
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "9.0.2"
URL = f"https://github.com/GyanD/codexffmpeg/releases/download/{VERSION}/ffmpeg-{VERSION}-essentials_build.zip"
SHA256 = "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"  # gyan.dev'in yayınladığı özet
FILES = {  # arşivdeki ad → vendor/ içindeki ad
    "bin/ffmpeg.exe": "ffmpeg.exe",
    "bin/ffprobe.exe": "ffprobe.exe",
    "LICENSE": "FFMPEG-LICENSE.txt",
    "README.txt": "FFMPEG-README.txt",
}
VENDOR = Path(__file__).resolve().parent.parent / "vendor"


def download(path):
    print(f"İndiriliyor: {URL}")
    with urllib.request.urlopen(URL, timeout=60) as response, open(path, "wb") as file:
        while chunk := response.read(1 << 20):
            file.write(chunk)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while chunk := file.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if all((VENDOR / name).is_file() for name in FILES.values()):
        print("FFmpeg zaten vendor/ klasöründe.")
        return 0
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "ffmpeg.zip"
        download(archive)
        if sha256_of(archive) != SHA256:
            print("HATA: SHA-256 özeti tutmuyor; dosya kullanılmadı.", file=sys.stderr)
            return 1
        VENDOR.mkdir(exist_ok=True)
        prefix = f"ffmpeg-{VERSION}-essentials_build/"
        with zipfile.ZipFile(archive) as zip_file:
            for source, target in FILES.items():
                (VENDOR / target).write_bytes(zip_file.read(prefix + source))
    print(f"Hazır: {VENDOR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
