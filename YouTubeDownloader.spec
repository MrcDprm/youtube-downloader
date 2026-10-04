# -*- mode: python ; coding: utf-8 -*-
# Derleme: önce  python scripts/fetch_ffmpeg.py  (vendor/ klasörüne FFmpeg),
# sonra  python -m PyInstaller YouTubeDownloader.spec  →  dist/YouTubeDownloader/
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

# Sürüm bilgileri (updater.bundled_version için) ve yt-dlp-ejs'in JavaScript dosyaları pakete girer
datas = [('assets', 'assets'), ('vendor/FFMPEG-LICENSE.txt', 'vendor'), ('vendor/FFMPEG-README.txt', 'vendor')]
datas += copy_metadata('yt-dlp') + copy_metadata('yt-dlp-ejs') + collect_data_files('yt_dlp_ejs')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('vendor/ffmpeg.exe', 'vendor'), ('vendor/ffprobe.exe', 'vendor')],
    datas=datas,
    hiddenimports=['yt_dlp_ejs'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'cryptography'],  # başka paketlerin isteğe bağlı bağımlılıkları; bu uygulamada gerekmiyor
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YouTubeDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='YouTubeDownloader',
)
