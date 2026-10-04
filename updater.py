"""yt-dlp'yi, onun JavaScript betiklerini (yt-dlp-ejs) ve Deno'yu güncel tutar.

YouTube sık sık değiştiği için yt-dlp birkaç haftada bir yeni sürüm çıkarır. Uygulama yeni sürümü PyPI'den
(Python paketlerinin resmi deposu) indirir, SHA-256 özetini PyPI'nin verdiği özetle karşılaştırır ve kullanıcı
klasörüne kaydeder. Bir sonraki içe aktarmada bu sürüm kullanılır; kurulumla gelen sürüm yedekte kalır.

İndirilen paketler (.whl) aslında zip dosyasıdır; Python saf Python paketlerini zip'ten doğrudan içe aktarabilir.
"""
import hashlib
import importlib.metadata
import json
import re
import sys
import time
import urllib.request
import zipfile

from app_info import VERSION
from storage import DATA_DIR, load_json, save_json

PYPI_URL = "https://pypi.org/pypi/{name}/json"
PYPI_VERSION_URL = "https://pypi.org/pypi/{name}/{version}/json"
DOWNLOAD_HOST = "https://files.pythonhosted.org/"
MANIFEST_FILE = "packages.json"
PACKAGES = DATA_DIR / "packages"
CHECK_EVERY_SECONDS = 12 * 60 * 60
TIMEOUT_SECONDS = 20
MAX_JSON_BYTES = 5_000_000
MAX_SIZES = {"yt-dlp": 30_000_000, "yt-dlp-ejs": 5_000_000, "deno": 150_000_000}
SAFE_NAME = re.compile(r"[A-Za-z0-9_.+-]{1,120}")
CHUNK = 1 << 16


class UpdateError(Exception):
    """Güncelleme yapılamadı (bağlantı yok, beklenmeyen yanıt, özet tutmuyor)."""


def parse_version(text):
    """"2026.08.19" → (2026, 8, 19). Sayı olmayan parçalar ("rc1" gibi) olan sürümler kabul edilmez."""
    if not isinstance(text, str) or not re.fullmatch(r"\d+(\.\d+){0,3}", text):
        return None
    return tuple(int(part) for part in text.split("."))


def python_supported(requires_python, current=sys.version_info[:2]):
    """">=3.10" gibi koşulları kontrol eder; anlaşılmayan koşulda güvenli tarafta kalıp hayır der."""
    if not requires_python:
        return True
    for condition in requires_python.split(","):
        match = re.fullmatch(r"\s*(>=|<|<=|>|!=|==)\s*(\d+)\.(\d+)(\.\*|\.\d+)?\s*", condition)
        if not match:
            return False
        operator, version = match.group(1), (int(match.group(2)), int(match.group(3)))
        if operator == "!=" and match.group(4) == ".*":
            ok = current != version
        else:
            ok = {">=": current >= version, ">": current > version, "<": current < version,
                  "<=": current <= version, "==": current == version, "!=": current != version}[operator]
        if not ok:
            return False
    return True


def requirement(requires_dist, name):
    """yt-dlp'nin bağımlılık listesinden bir paketin koşulu: ("==", (0, 8, 0)) ya da (">=", (2, 6, 6))."""
    for line in requires_dist or []:
        match = re.match(rf"{re.escape(name)}\s*(==|>=)\s*([\d.]+)", line) if isinstance(line, str) else None
        if match and parse_version(match.group(2)):
            return match.group(1), parse_version(match.group(2))
    return None


def pick_wheel(release, platform=None):
    """PyPI yanıtından uygun .whl dosyası: adı, adresi, boyutu ve SHA-256 özeti."""
    info = release.get("info") if isinstance(release, dict) else None
    version = info.get("version") if isinstance(info, dict) else None
    if not parse_version(version):
        raise UpdateError("unexpected version")
    for file in release.get("urls") or []:
        if not isinstance(file, dict) or file.get("packagetype") != "bdist_wheel":
            continue
        name, url, size = file.get("filename"), file.get("url"), file.get("size")
        digest = (file.get("digests") or {}).get("sha256")
        if platform and platform not in str(name):
            continue
        if (isinstance(name, str) and SAFE_NAME.fullmatch(name) and isinstance(url, str)
                and url.startswith(DOWNLOAD_HOST) and isinstance(size, int)
                and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)):
            return {"name": name, "url": url, "size": size, "sha256": digest, "version": version,
                    "requires_dist": info.get("requires_dist") or [],
                    "requires_python": info.get("requires_python")}
    raise UpdateError("no wheel")


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": f"YouTubeDownloader/{VERSION}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_JSON_BYTES + 1)
    if len(body) > MAX_JSON_BYTES:
        raise UpdateError("response too large")
    try:
        return json.loads(body)
    except ValueError:
        raise UpdateError("invalid JSON") from None


def download_file(wheel, limit, on_progress=None):
    """Dosyayı indirir, boyutunu ve SHA-256 özetini kontrol eder; ancak ikisi de tutarsa yerine koyar."""
    if wheel["size"] > limit:
        raise UpdateError("file too large")
    PACKAGES.mkdir(parents=True, exist_ok=True)
    target = PACKAGES / wheel["name"]
    temp = target.with_name(target.name + ".tmp")
    digest = hashlib.sha256()
    received = 0
    request = urllib.request.Request(wheel["url"], headers={"User-Agent": f"YouTubeDownloader/{VERSION}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response, open(temp, "wb") as file:
            while chunk := response.read(CHUNK):
                received += len(chunk)
                if received > wheel["size"]:
                    break
                digest.update(chunk)
                file.write(chunk)
                if on_progress:
                    on_progress(received, wheel["size"])
    except BaseException:  # bağlantı koptu ya da uygulama kapandı: yarım dosya kalmasın
        temp.unlink(missing_ok=True)
        raise
    if received != wheel["size"] or digest.hexdigest() != wheel["sha256"]:
        temp.unlink(missing_ok=True)
        raise UpdateError("checksum mismatch")
    temp.replace(target)
    return target


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while chunk := file.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()

def bundled_version(name):
    """Kurulumla gelen sürüm; bilinmiyorsa (0,)."""
    try:
        return parse_version(importlib.metadata.version(name)) or (0,)
    except importlib.metadata.PackageNotFoundError:
        return (0,)


def installed(manifest, name):
    """Kullanıcı klasöründeki kayıtlı paket: dosya hâlâ duruyor ve özeti kayıtla aynıysa."""
    entry = manifest.get(name)
    if not isinstance(entry, dict) or not isinstance(entry.get("file"), str) or not SAFE_NAME.fullmatch(entry["file"]):
        return None
    path = PACKAGES / entry["file"]
    version = parse_version(entry.get("version"))
    if not version or not path.is_file() or sha256_of(path) != entry.get("sha256"):
        return None
    return {"path": path, "version": version}


def current_version(manifest, name):
    entry = installed(manifest, name)
    return max(entry["version"], bundled_version(name)) if entry else bundled_version(name)


def update_package(manifest, name, wheel, on_progress=None):
    path = download_file(wheel, MAX_SIZES[name], on_progress)
    manifest[name] = {"file": path.name, "version": wheel["version"], "sha256": wheel["sha256"]}


def update_deno(manifest, wheel, on_progress=None):
    """Deno paketinin içindeki deno.exe çıkarılır; sürümlü adla kaydedilir (çalışan eski kopya ezilmez)."""
    archive = download_file(wheel, MAX_SIZES["deno"], on_progress)
    with zipfile.ZipFile(archive) as zip_file:
        member = next((item for item in zip_file.infolist() if item.filename.endswith("/deno.exe")), None)
        if member is None or member.file_size > MAX_SIZES["deno"] * 4:
            raise UpdateError("no deno.exe")
        target = PACKAGES / f"deno-{wheel['version']}.exe"
        target.write_bytes(zip_file.read(member))
    archive.unlink(missing_ok=True)
    manifest["deno"] = {"file": target.name, "version": wheel["version"], "sha256": sha256_of(target)}


def check_for_updates(now=None, fetch_json=get_json, on_progress=None, force=False):
    """Gerekiyorsa yt-dlp, yt-dlp-ejs ve Deno'yu indirir. Güncellenen paketlerin adlarını döndürür.

    Her açılışta PyPI'ye gidilmez; son kontrol 12 saatten yeniyse ve her şey yerindeyse hiçbir şey yapılmaz.
    """
    now = time.time() if now is None else now
    manifest = load_json(MANIFEST_FILE, {})
    manifest = manifest if isinstance(manifest, dict) else {}
    checked_at = manifest.get("checked_at")
    recent = isinstance(checked_at, (int, float)) and 0 <= now - checked_at < CHECK_EVERY_SECONDS
    if recent and not force and installed(manifest, "deno"):
        return []

    updated = []
    latest = pick_wheel(fetch_json(PYPI_URL.format(name="yt-dlp")))
    usable = python_supported(latest["requires_python"])  # yeni sürüm bu Python'da çalışmıyorsa eskisi kalır
    if usable and parse_version(latest["version"]) > current_version(manifest, "yt-dlp"):
        update_package(manifest, "yt-dlp", latest)
        updated.append("yt-dlp")

    # yt-dlp belirli bir yt-dlp-ejs sürümü ister ("yt-dlp-ejs==0.8.0"); tam olarak o sürüm kurulur
    ejs = requirement(latest["requires_dist"], "yt-dlp-ejs") if usable else None
    if ejs and ejs[0] == "==" and current_version(manifest, "yt-dlp-ejs") != ejs[1]:
        version = ".".join(map(str, ejs[1]))
        update_package(manifest, "yt-dlp-ejs", pick_wheel(fetch_json(PYPI_VERSION_URL.format(name="yt-dlp-ejs", version=version))))
        updated.append("yt-dlp-ejs")

    deno = installed(manifest, "deno")
    minimum = requirement(latest["requires_dist"], "deno")
    if deno is None or (minimum and deno["version"] < minimum[1]):
        update_deno(manifest, pick_wheel(fetch_json(PYPI_URL.format(name="deno")), platform="win_amd64"), on_progress)
        updated.append("deno")

    manifest["checked_at"] = int(now)
    save_json(MANIFEST_FILE, manifest)
    remove_unused(manifest)
    return updated


def remove_unused(manifest):
    """Artık kullanılmayan eski sürümleri siler; kullanımda olan dosya silinemezse sonraki sefere kalır."""
    keep = {entry["file"] for entry in manifest.values() if isinstance(entry, dict) and "file" in entry}
    for path in PACKAGES.glob("*"):
        if path.name not in keep:
            try:
                path.unlink()
            except OSError:
                pass


def activate():
    """Kayıtlı ve özeti doğrulanmış yt-dlp sürümlerini içe aktarma yoluna ekler; Deno'nun yolunu döndürür.

    yt_dlp içe aktarılmadan önce çağrılmalıdır; zaten içe aktarıldıysa yeni sürüm bir sonraki açılışta kullanılır.
    """
    manifest = load_json(MANIFEST_FILE, {})
    manifest = manifest if isinstance(manifest, dict) else {}
    for name in ("yt-dlp-ejs", "yt-dlp"):
        entry = installed(manifest, name)
        if entry and entry["version"] >= bundled_version(name) and str(entry["path"]) not in sys.path:
            sys.path.insert(0, str(entry["path"]))
    deno = installed(manifest, "deno")
    return deno["path"] if deno else None