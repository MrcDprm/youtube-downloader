"""yt-dlp ile bilgi alma ve indirme. Arayüzden bağımsızdır; arayüz bunları arka plan iş parçacığında çağırır.

yt_dlp burada, ilk kullanımda içe aktarılır: updater.activate() önce en yeni sürümü yükleyebilsin diye.
"""
import glob
from pathlib import Path

from links import canonical_url

MAX_PLAYLIST_ITEMS = 500

# yt-dlp'nin hata metnindeki ifadeler → kullanıcıya gösterilecek mesajın anahtarı (ilk eşleşen kazanır)
ERROR_PATTERNS = (
    ("Private video", "private"),
    ("Sign in to confirm your age", "age_restricted"),
    ("age-restricted", "age_restricted"),
    ("not available in your country", "region_locked"),
    ("members-only", "members_only"),
    ("Join this channel", "members_only"),
    ("This live event will begin", "live_upcoming"),
    ("is offline", "live_upcoming"),
    ("Premieres in", "live_upcoming"),
    ("Sign in to confirm you", "blocked"),  # "…you're not a bot": YouTube bu bağlantıyı geçici olarak engelledi
    ("HTTP Error 429", "blocked"),
    ("Video unavailable", "unavailable"),
    ("recording is not available", "unavailable"),
    ("This video is unavailable", "unavailable"),
    ("has been removed", "unavailable"),
    ("does not exist", "unavailable"),
    ("No space left on device", "disk_full"),
    ("Permission denied", "permission"),
    ("Unable to download", "network"),
    ("timed out", "network"),
    ("getaddrinfo failed", "network"),
    ("Connection", "network"),
    ("ffmpeg is not installed", "ffmpeg_missing"),
    ("ffmpeg not found", "ffmpeg_missing"),
)


class DownloadFailed(Exception):
    """Bilgi alma ya da indirme başarısız. code, i18n'deki mesajın anahtarıdır."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Cancelled(Exception):
    """Kullanıcı durdurdu; ilerleme bildiriminden fırlatılır ve yt-dlp indirmeyi keser."""


class SilentLogger:
    """yt-dlp'nin konsola yazmasını engeller; hatalar istisna olarak zaten bize gelir."""

    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


def classify_error(message):
    for pattern, code in ERROR_PATTERNS:
        if pattern.lower() in message.lower():
            return code
    return "failed"


def _text(value, limit=300):
    return value[:limit] if isinstance(value, str) and value else None


def _seconds(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


def video_entry(raw):
    """yt-dlp'nin video bilgisinden kuyruğa girecek sade kayıt. Sadece beklenen türdeki alanlar alınır."""
    video_id = raw.get("id") if isinstance(raw, dict) else None
    if not isinstance(video_id, str) or len(video_id) != 11:
        return None
    return {
        "id": video_id,
        "url": canonical_url("video", video_id),
        "title": _text(raw.get("title")) or video_id,
        "channel": _text(raw.get("channel") or raw.get("uploader"), 100),
        "duration": _seconds(raw.get("duration")),
        "is_live": raw.get("live_status") in ("is_live", "is_upcoming"),
    }


def base_options(js_runtime=None):
    options = {"quiet": True, "no_warnings": True, "noprogress": True, "logger": SilentLogger()}
    if js_runtime:
        options["js_runtimes"] = {"deno": {"path": str(js_runtime)}}
    return options


def fetch_info(url, kind, js_runtime=None):
    """Linkteki video(lar)ın listesi. Oynatma listesinde videolar tek tek açılmaz (hızlı)."""
    import yt_dlp

    options = base_options(js_runtime)
    if kind == "playlist":
        options.update(extract_flat="in_playlist", playlistend=MAX_PLAYLIST_ITEMS)
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            raw = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as error:
        raise DownloadFailed(classify_error(str(error))) from None
    entries = raw.get("entries") if kind == "playlist" else [raw]
    videos = [video for video in map(video_entry, entries or []) if video]
    if not videos:
        raise DownloadFailed("empty_playlist" if kind == "playlist" else "unavailable")
    return videos

class Download:
    """Tek bir videonun indirilmesi. run() bitene kadar bekler; cancel() başka iş parçacığından çağrılır."""

    def __init__(self, url, options, on_progress=None):
        self.url = url
        self.options = options
        self.on_progress = on_progress  # (aşama, yüzde, hız bayt/sn ya da None, kalan saniye ya da None)
        self.cancelled = False
        self.parts = 1
        self.part = 0
        self.current_file = None
        self.temp_files = set()
        self.final_file = None

    def _progress_hook(self, data):
        # Dosya adları önce kaydedilir: durdurulursa temizlenecek parçalar bilinsin
        for key in ("tmpfilename", "filename"):
            if data.get(key):
                self.temp_files.add(data[key])
        if self.cancelled:
            raise Cancelled()
        filename = data.get("filename")
        if filename and filename != self.current_file:
            if self.current_file is not None:
                self.part = min(self.part + 1, self.parts - 1)
            self.current_file = filename
        if data.get("status") != "downloading" or not self.on_progress:
            return
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        fraction = min(1.0, data.get("downloaded_bytes", 0) / total) if total else 0.0
        percent = (self.part + fraction) / self.parts * 100
        self.on_progress("downloading", percent, data.get("speed"), data.get("eta"))

    def _postprocessor_hook(self, data):
        if data.get("status") == "started" and self.on_progress:
            self.on_progress("processing", 100.0, None, None)
        if data.get("status") == "finished":
            filepath = (data.get("info_dict") or {}).get("filepath")
            if filepath:
                self.final_file = filepath

    def run(self):
        """İndirir; ("done", dosya yolu), ("exists", dosya yolu), ("cancelled", None) ya da (hata anahtarı, None) döner."""
        import yt_dlp

        options = dict(self.options, progress_hooks=[self._progress_hook],
                       postprocessor_hooks=[self._postprocessor_hook])
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if info.get("live_status") in ("is_live", "is_upcoming"):
                    return "live", None  # canlı yayın bitmeden indirme de bitmez
                self.parts = len(info.get("requested_formats") or [None])
                target = Path(ydl.prepare_filename(info))
                final = self._final_name(target)
                if final.exists():
                    return "exists", final
                ydl.process_ie_result(info, download=True)
        except Cancelled:
            self._clean_up()
            return "cancelled", None
        except yt_dlp.utils.DownloadError as error:
            if isinstance(error.exc_info[1] if error.exc_info else None, Cancelled) or self.cancelled:
                self._clean_up()
                return "cancelled", None
            self._clean_up()
            return classify_error(str(error)), None
        except OSError as error:
            self._clean_up()
            return classify_error(str(error)), None
        return "done", Path(self.final_file) if self.final_file else final

    def _final_name(self, target):
        """Birleştirme ya da ses dönüştürme sonrası oluşacak dosyanın adı."""
        processors = self.options.get("postprocessors") or []
        for processor in processors:
            if processor.get("key") == "FFmpegExtractAudio":
                return target.with_suffix("." + processor["preferredcodec"])
        if self.options.get("merge_output_format") and self.parts > 1:
            return target.with_suffix("." + self.options["merge_output_format"])
        return target

    def cancel(self):
        self.cancelled = True

    def _clean_up(self):
        """Yarım kalan parçaları (.part, .ytdl, parça parça inen "-Frag" dosyaları, birleştirilmemiş görüntü/ses) siler."""
        for name in self.temp_files:
            path = Path(name)
            # glob.escape: başlıktaki [ ] gibi karakterler dosya adı kalıbı sanılmasın ("Şarkı [Official Video]")
            fragments = path.parent.glob(glob.escape(path.name) + ".part-Frag*")
            leftovers = [path, Path(name + ".part"), Path(name + ".ytdl"), *fragments]
            for leftover in leftovers:
                try:
                    leftover.unlink(missing_ok=True)
                except OSError:
                    pass