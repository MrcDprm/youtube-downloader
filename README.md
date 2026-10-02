# YouTube Downloader

**English** | [Türkçe](README.tr.md)

A desktop app written in Python and Tkinter for downloading YouTube videos, playlists and audio with [yt-dlp](https://github.com/yt-dlp/yt-dlp). It keeps itself working by updating yt-dlp on its own.

> 🚧 Work in progress. This README is the project plan and will be completed at v1.0.0.

> ⚠️ **For personal use only.** Download only videos you own or have permission to download, and respect YouTube's Terms of Service and copyright law.

## Plan

### MVP
- **Paste a link:** a video or playlist link is detected (also from the clipboard). Title, channel, duration and thumbnail are shown before downloading.
- **Video or audio:** video as MP4 in the chosen quality (best, 2160p, 1440p, 1080p, 720p, 480p, 360p); audio as MP3 or M4A.
- **Playlists:** every video in the playlist is added to the queue.
- **Queue:** downloads run one after another with percentage, speed and time left; one button stops the queue.
- **Safe output:** existing files are never overwritten, file names are made safe for Windows, unfinished files are cleaned up. Only YouTube links are accepted.
- **Keeps working:** at startup the app checks for a new yt-dlp version and installs it in the background (version and SHA-256 hash from PyPI). The JavaScript runtime YouTube now requires (Deno) is downloaded the same way on first use.
- **Clear errors:** private, deleted, age-restricted or region-locked videos and network problems get readable messages.
- **Usability:** output folder (Downloads by default), "open folder", dark and light theme, Turkish and English, remembered settings.
- **Desktop app:** icon, version, About window with the personal-use note, settings saved in the user's folder, Windows installer with FFmpeg included (PyInstaller + Inno Setup).
- **Tests:** link checks, format selection, progress parsing, update and hash checks, settings.

### Future Plans
- Subtitles.
- Choosing a part of the video (start / end time).
- Downloading several videos at the same time.
- Channel downloads.

## Tech Stack
- Python 3, Tkinter
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (used as a library) and [Deno](https://deno.com) for YouTube's JavaScript
- [FFmpeg](https://ffmpeg.org) for merging video and audio and for MP3
- [Pillow](https://python-pillow.org) for thumbnails
- `unittest`
- PyInstaller, Inno Setup
