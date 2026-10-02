"""YouTube linklerini tanır ve sadeleştirir. Sadece YouTube adresleri kabul edilir.

Kullanıcının yapıştırdığı metne güvenilmez: adres ayrıştırılır, alan adı ve kimlikler kontrol edilir,
yt-dlp'ye her zaman tek biçimli, temiz bir adres verilir.
"""
import re
from urllib.parse import parse_qs, urlparse

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
SHORT_HOST = "youtu.be"
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
PLAYLIST_ID = re.compile(r"[A-Za-z0-9_-]{10,64}")
MAX_LINK_LENGTH = 500


class LinkError(ValueError):
    """Geçersiz link. code, i18n'deki mesajın anahtarıdır."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def parse_link(text):
    """Metni ("youtu.be/…", "https://www.youtube.com/watch?v=…&list=…") (tür, kimlik) çiftine çevirir.

    Tür "video" ya da "playlist" olur. İçinde hem video hem liste olan linklerde video seçilir;
    listenin tamamı için kullanıcı liste linkini yapıştırır (YouTube'daki "paylaş" davranışı da bu).
    """
    text = text.strip()
    if not text:
        raise LinkError("empty")
    if len(text) > MAX_LINK_LENGTH:
        raise LinkError("not_youtube")
    if "://" not in text:
        text = "https://" + text  # "youtube.com/watch?v=…" gibi şemasız yapıştırmalar
    try:
        url = urlparse(text)
    except ValueError:
        raise LinkError("not_youtube") from None
    host = (url.hostname or "").lower()
    if url.scheme not in ("http", "https") or (host not in YOUTUBE_HOSTS and host != SHORT_HOST):
        raise LinkError("not_youtube")

    query = parse_qs(url.query)
    parts = [part for part in url.path.split("/") if part]
    if host == SHORT_HOST:
        video_id = parts[0] if parts else ""
    elif parts[:1] == ["watch"]:
        video_id = query.get("v", [""])[0]
    elif parts[:1] in (["shorts"], ["live"], ["embed"]) and len(parts) > 1:
        video_id = parts[1]
    elif parts[:1] == ["playlist"]:
        video_id = ""
    else:
        raise LinkError("unsupported")

    if VIDEO_ID.fullmatch(video_id):
        return "video", video_id
    playlist_id = query.get("list", [""])[0]
    if PLAYLIST_ID.fullmatch(playlist_id):
        return "playlist", playlist_id
    raise LinkError("unsupported")


def canonical_url(kind, item_id):
    if kind == "video":
        return f"https://www.youtube.com/watch?v={item_id}"
    return f"https://www.youtube.com/playlist?list={item_id}"