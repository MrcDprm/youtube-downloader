"""Kuyruktaki videoların küçük resimleri: YouTube'un resim sunucusundan indirilip küçültülür.

Adres video kimliğinden üretilir (yt-dlp'nin verdiği adrese güvenilmez); boyut ve biçim sınırlıdır.
"""
import io
import urllib.request

from PIL import Image, ImageOps

from links import VIDEO_ID

THUMBNAIL_URL = "https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"  # 320×180
MAX_BYTES = 500_000
TIMEOUT_SECONDS = 10
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def fetch_thumbnail(video_id, size, opener=urllib.request.urlopen):
    """Verilen boyuta kırpılıp küçültülmüş resim; alınamazsa None. Resim olmadan da uygulama çalışır."""
    if not VIDEO_ID.fullmatch(video_id):
        return None
    try:
        with opener(THUMBNAIL_URL.format(video_id=video_id), timeout=TIMEOUT_SECONDS) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return None
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ALLOWED_FORMATS:
                return None
            return ImageOps.fit(image.convert("RGB"), size, Image.LANCZOS)
    except (OSError, ValueError, Image.DecompressionBombError):  # ağ hatası, bozuk ya da tuhaf resim
        return None