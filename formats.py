"""İndirme seçenekleri: video kalitesi ya da ses formatı yt-dlp ayarlarına çevrilir.

Kullanıcı "1080p" ya da "MP3" seçer; yt-dlp'nin format dili ve sonradan işleme (FFmpeg) adımları burada kurulur.
"""

VIDEO_QUALITIES = {"best": None, "2160p": 2160, "1440p": 1440, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
AUDIO_FORMATS = {"mp3": "MP3", "m4a": "M4A (AAC)"}
MP3_QUALITY = "192"  # kbps
MAX_NAME_LENGTH = 150  # Windows'un 260 karakterlik yol sınırına takılmamak için


def download_options(mode, choice, folder, ffmpeg_folder):
    """yt-dlp'nin YoutubeDL'ine verilecek ayarlar. mode: "video" ya da "audio"."""
    options = {
        "paths": {"home": str(folder)},
        "outtmpl": {"default": "%(title)s.%(ext)s"},
        "windowsfilenames": True,  # \ / : * ? " < > | gibi karakterler dosya adından çıkarılır
        "trim_file_name": MAX_NAME_LENGTH,
        "overwrites": False,
        "noplaylist": True,  # her indirme tek video; listeler kuyruğa ayrı ayrı eklenir
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ffmpeg_location": str(ffmpeg_folder) if ffmpeg_folder else None,
    }
    if mode == "video":
        height = VIDEO_QUALITIES[choice]
        # En iyi görüntü + en iyi ses; aynı çözünürlükte H.264 ve AAC tercih edilir (her yerde açılır)
        options["format"] = "bv*+ba/b"
        options["format_sort"] = ([f"res:{height}"] if height else []) + ["vcodec:h264", "acodec:aac"]
        options["merge_output_format"] = "mp4"
    else:
        options["format"] = "ba/b"
        processor = {"key": "FFmpegExtractAudio", "preferredcodec": choice}
        if choice == "mp3":
            processor["preferredquality"] = MP3_QUALITY
        options["postprocessors"] = [processor, {"key": "FFmpegMetadata"}]
    return options