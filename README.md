<p align="center">
  <img src="assets/icon.png" alt="YouTube Downloader icon" width="96">
</p>

<h1 align="center">YouTube Downloader</h1>

<p align="center">
  <b>English</b> | <a href="README.tr.md">Türkçe</a>
</p>

<p align="center">
  A desktop app written in Python and Tkinter for downloading YouTube videos, playlists and audio with yt-dlp.<br>
  It keeps working after release by updating yt-dlp and the JavaScript runtime YouTube now requires on its own.
</p>

<p align="center">
  <a href="https://github.com/MrcDprm/youtube-downloader/releases/latest"><b>⬇️ Download for Windows</b></a>
</p>

<p align="center">
  <img src="docs/demo.gif" alt="Animation showing a link being pasted and the video downloading with progress" width="720">
</p>

> ⚠️ **For personal use only.** Download only videos you own or have permission to download, and respect YouTube's Terms of Service and copyright law. The app does not sign in to YouTube and cannot download private, members-only or DRM-protected content.

## Features

**Downloading**
- Paste a video, Short or playlist link; title, channel, length and thumbnail appear before downloading
- A YouTube link on the clipboard is pasted for you when you switch back to the app
- **Video** as MP4 in the best quality or 2160p, 1440p, 1080p, 720p, 480p, 360p; H.264 + AAC is preferred so files play everywhere
- **Audio** as MP3 (192 kbps) or M4A, with title and channel written into the file's tags
- Playlists add every video to the queue; duplicates are skipped
- Downloads run one after another with percentage, speed and time left; one button stops the queue

**Keeps working**
- YouTube changes often, so yt-dlp releases a new version every few weeks. At startup the app checks PyPI, downloads a newer yt-dlp in the background, **verifies its SHA-256 hash** and uses it right away
- YouTube now requires a JavaScript runtime; [Deno](https://deno.com) is downloaded and verified the same way on first use
- Without internet the app keeps working with the version it was installed with

**Safety**
- Only YouTube links are accepted; everything else is rejected before reaching yt-dlp
- Existing files are never overwritten; file names are made safe for Windows
- Stopping a download deletes its unfinished parts
- Clear messages for private, removed, age-restricted, region-locked and live videos, blocked requests and network errors

**Interface**
- Output folder (Downloads by default), "Open folder", double-click a finished video to show it in Explorer
- Dark and light theme, Turkish and English interface, remembered settings

**Other**
- 33 unit tests, none of which need an internet connection
- Setup wizard with FFmpeg included

## Screenshots

**Downloading a playlist (dark, Turkish)**

<img src="docs/queue-dark.png" alt="Playlist queue with three downloaded videos, one downloading with speed and time left, and a removed video in red" width="720">

| Audio downloads (light, English) | Empty window |
|---|---|
| <img src="docs/audio-light-en.png" alt="Four videos downloaded as MP3 in light theme" width="420"> | <img src="docs/empty-dark.png" alt="Empty window inviting to paste a link" width="420"> |

## Installation

1. Download `YouTubeDownloader-x.y.z-Setup.exe` from the [Releases](https://github.com/MrcDprm/youtube-downloader/releases/latest) page.
2. Run it and follow the setup steps. No administrator rights are needed. FFmpeg is included.
3. Find the app in the Start menu as **YouTube İndirici**. The interface opens in Turkish; the language button at the top right switches it to English.
4. On first launch the app downloads Deno (about 42 MB) once; the bottom line shows the progress.

> **Windows "protected your PC" warning:** The app is not digitally signed, so Windows SmartScreen may show a warning on first launch. Continue with **More info → Run anyway**. The full source code is open in this repository.

**Uninstall:** Settings → Apps → Installed apps → YouTube İndirici → Uninstall.
Settings and the downloaded components are kept in `%USERPROFILE%\.youtube-downloader` and can be deleted by hand.

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Enter` (in the link box) | Add the link |
| `Delete` (in the list) | Remove the selected videos |
| `Ctrl+Enter` | Start or stop downloading |

## Tech Stack

- **Python 3.12** and **Tkinter / ttk**: user interface
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** (used as a library) and **[Deno](https://deno.com)**: talking to YouTube
- **[FFmpeg](https://ffmpeg.org)**: merging video and audio, MP3 conversion
- **[Pillow](https://python-pillow.org)**: thumbnails
- **urllib, hashlib, zipfile**: verified self-updates from PyPI
- **threading, queue**: background work
- **unittest**: tests
- **PyInstaller** and **Inno Setup**: Windows installer

## Project Structure

```
youtube-downloader/
├── main.py          # Entry point
├── gui.py           # Tkinter interface: link box, queue, options, progress
├── links.py         # Recognizes and cleans YouTube links
├── formats.py       # Quality and audio choices as yt-dlp options
├── downloader.py    # Video info, downloading, progress, stopping, error messages
├── updater.py       # Keeps yt-dlp, its scripts and Deno up to date from PyPI
├── thumbnails.py    # Downloads and resizes thumbnails
├── settings.py      # Remembered options
├── i18n.py          # Turkish and English texts
├── storage.py       # Saves JSON files to the user folder
├── app_info.py      # App name, version, FFmpeg lookup
├── scripts/         # Downloads a verified FFmpeg build for packaging
├── assets/          # App icon
├── docs/            # README images
├── installer/       # Inno Setup script
└── tests/           # Tests
```

## Running from Source

Requires Python 3.12 or newer and FFmpeg on the `PATH` (for example `winget install Gyan.FFmpeg`).

```bash
python -m pip install yt-dlp yt-dlp-ejs pillow
python main.py           # run the app (Deno is downloaded on first start)
python -m unittest -v    # run the tests
```

### Building the installer

Requires [PyInstaller](https://pyinstaller.org) and [Inno Setup 6](https://jrsoftware.org/isinfo.php).

```bash
python scripts/fetch_ffmpeg.py    # downloads FFmpeg into vendor/ and checks its SHA-256
python -m PyInstaller --noconfirm YouTubeDownloader.spec
ISCC installer/youtube-downloader.iss
```

The installer is created in the `installer/Output/` folder.

**When releasing a new version:** update the version number in both `app_info.py` (`VERSION`) and `installer/youtube-downloader.iss` (`AppVersion`), run the tests, run the build commands and upload the installer to a new GitHub Release.

## What I Learned

- **Software that depends on someone else's website goes stale.** YouTube changes constantly, so a downloader frozen at release would break within weeks. I made the app update yt-dlp by itself: it reads the latest version from PyPI's JSON API, downloads the package, checks its SHA-256 hash and loads it. I learned that a wheel (`.whl`) is just a zip file and Python can import from it directly by putting it at the front of `sys.path`.
- **Downloaded code must be verified.** Because the app runs code it downloads, it checks the size, the host, the file name and the hash before using anything, and checks the hash again before every load. A file that was changed on disk is ignored.
- **Order of imports matters.** Python caches a module after the first import, so yt-dlp is imported inside functions, only after the updater has had a chance to activate the newest version.
- **Using a library through hooks.** yt-dlp reports progress through callback functions. I combined the separate video and audio downloads into one smooth percentage, computed my own time left, and stopped downloads by raising an exception from inside the hook.
- **Not trusting user input or remote data.** Links are parsed and checked against an exact list of YouTube hosts, so look-alike domains and other sites never reach yt-dlp. Titles from YouTube are cleaned before becoming file names, and thumbnails are size- and format-checked.
- **Keeping the window responsive.** Updating, reading video info, loading thumbnails and downloading each run in their own thread and report back through a queue. A `threading.Event` makes the info reader wait until the components are ready.
- **Turning technical errors into helpful messages.** yt-dlp only gives error text, so I matched known phrases to clear messages (private, age-restricted, region-locked, blocked), and a test with YouTube's real wording caught a pattern that did not match.
- **Small details make a difference.** Pasting a link from the clipboard automatically, letting "Download" be pressed while a link is still being read, and keeping thumbnail images referenced so Tkinter does not lose them were all things I found while using the app.

## Future Plans

- Subtitles
- Downloading part of a video (start and end time)
- Several downloads at the same time
- Channel downloads
- Packages for macOS and Linux

## License

[MIT](LICENSE) © 2026 Miraç Deprem

The installer includes [FFmpeg](https://ffmpeg.org) (GPL v3, static build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)); its license and source link are installed in the `vendor` folder. [yt-dlp](https://github.com/yt-dlp/yt-dlp) is released under the Unlicense and [Deno](https://github.com/denoland/deno) under the MIT license.
