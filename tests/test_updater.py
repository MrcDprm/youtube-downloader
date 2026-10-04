import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import storage
import updater
from updater import UpdateError, parse_version, pick_wheel, python_supported, requirement

HOST = "https://files.pythonhosted.org/packages/"


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def release(version, filename, data, requires_dist=(), requires_python=">=3.10", **changes):
    file = {"filename": filename, "url": HOST + filename, "size": len(data), "packagetype": "bdist_wheel",
            "digests": {"sha256": hashlib.sha256(data).hexdigest()}}
    file.update(changes)
    return {"info": {"version": version, "requires_dist": list(requires_dist), "requires_python": requires_python},
            "urls": [{"filename": filename + ".tar.gz", "packagetype": "sdist"}, file]}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class TestParsing(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("2026.08.19"), (2026, 8, 19))
        self.assertGreater(parse_version("2026.10.5"), parse_version("2026.9.30"))
        for text in ("2026.8.19rc1", "", "v1", None, 5, "1..2"):
            with self.subTest(text=text):
                self.assertIsNone(parse_version(text))

    def test_python_supported(self):
        self.assertTrue(python_supported(None, (3, 12)))
        self.assertTrue(python_supported(">=3.10", (3, 12)))
        self.assertFalse(python_supported(">=3.13", (3, 12)))
        self.assertTrue(python_supported(">=3.9, !=3.11.*", (3, 12)))
        self.assertFalse(python_supported(">=3.9, !=3.12.*", (3, 12)))
        self.assertFalse(python_supported("~=3.12", (3, 12)))  # anlaşılmayan koşulda hayır

    def test_requirement(self):
        requires = ['brotli; extra == "default"', 'yt-dlp-ejs==0.8.0; extra == "default"', 'deno>=2.6.6; extra == "deno"']
        self.assertEqual(requirement(requires, "yt-dlp-ejs"), ("==", (0, 8, 0)))
        self.assertEqual(requirement(requires, "deno"), (">=", (2, 6, 6)))
        self.assertIsNone(requirement(requires, "missing"))
        self.assertIsNone(requirement([None, 5], "deno"))

    def test_pick_wheel(self):
        wheel = pick_wheel(release("1.2.3", "pkg-1.2.3-py3-none-any.whl", b"data"))
        self.assertEqual((wheel["name"], wheel["size"], wheel["version"]), ("pkg-1.2.3-py3-none-any.whl", 4, "1.2.3"))

    def test_pick_wheel_rejects_untrusted_files(self):
        cases = [
            release("1.0", "../../evil.whl", b"x"),
            release("1.0", "pkg.whl", b"x", url="https://evil.example/pkg.whl"),
            release("1.0", "pkg.whl", b"x", digests={"sha256": "not-a-hash"}),
            release("1.0", "pkg.whl", b"x", size="4"),
            release("1.0rc1", "pkg.whl", b"x"),
            {"info": None},
            None,
        ]
        for data in cases:
            with self.subTest(data=str(data)[:80]):
                with self.assertRaises(UpdateError):
                    pick_wheel(data)


class TestCheckForUpdates(unittest.TestCase):
    """PyPI ve indirmeler sahte; dosyalar gerçek kullanıcı klasörüne değil geçici bir klasöre yazılır."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        for target, value in ((storage, "DATA_DIR"), (updater, "PACKAGES")):
            patcher = mock.patch.object(target, value, self.folder / ("packages" if value == "PACKAGES" else ""))
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(updater, "bundled_version", lambda name: {"yt-dlp": (2026, 1, 1)}.get(name, (0,)))
        patcher.start()
        self.addCleanup(patcher.stop)

        self.ytdlp_data = make_zip({"yt_dlp/__init__.py": "VERSION = 'new'"})
        self.ejs_data = make_zip({"yt_dlp_ejs/__init__.py": ""})
        self.deno_data = make_zip({"deno-2.9.7.data/scripts/deno.exe": b"MZ fake deno"})
        self.releases = {
            updater.PYPI_URL.format(name="yt-dlp"): release(
                "2026.8.19", "yt_dlp-2026.8.19-py3-none-any.whl", self.ytdlp_data,
                ['yt-dlp-ejs==0.8.0; extra == "default"', 'deno>=2.6.6; extra == "deno"']),
            updater.PYPI_VERSION_URL.format(name="yt-dlp-ejs", version="0.8.0"): release(
                "0.8.0", "yt_dlp_ejs-0.8.0-py3-none-any.whl", self.ejs_data),
            updater.PYPI_URL.format(name="deno"): release("2.9.7", "deno-2.9.7-py3-none-win_amd64.whl", self.deno_data),
        }
        self.files = {self.releases[url]["urls"][1]["url"]: data for url, data in zip(
            self.releases, (self.ytdlp_data, self.ejs_data, self.deno_data))}
        patcher = mock.patch.object(updater.urllib.request, "urlopen",
                                    lambda request, timeout: FakeResponse(self.files[request.full_url]))
        patcher.start()
        self.addCleanup(patcher.stop)

    def fetch(self, url):
        return self.releases[url]

    def test_first_run_installs_everything(self):
        self.assertEqual(updater.check_for_updates(now=1000, fetch_json=self.fetch), ["yt-dlp", "yt-dlp-ejs", "deno"])
        names = sorted(path.name for path in updater.PACKAGES.iterdir())
        self.assertEqual(names, ["deno-2.9.7.exe", "yt_dlp-2026.8.19-py3-none-any.whl",
                                 "yt_dlp_ejs-0.8.0-py3-none-any.whl"])
        self.assertEqual((updater.PACKAGES / "deno-2.9.7.exe").read_bytes(), b"MZ fake deno")

    def test_recent_check_does_nothing(self):
        updater.check_for_updates(now=1000, fetch_json=self.fetch)
        self.assertEqual(updater.check_for_updates(now=2000, fetch_json=lambda url: self.fail("no request expected")), [])

    def test_nothing_new_after_interval(self):
        updater.check_for_updates(now=1000, fetch_json=self.fetch)
        later = 1000 + updater.CHECK_EVERY_SECONDS + 1
        self.assertEqual(updater.check_for_updates(now=later, fetch_json=self.fetch), [])

    def test_unsupported_python_keeps_current_version(self):
        url = updater.PYPI_URL.format(name="yt-dlp")
        self.releases[url]["info"]["requires_python"] = ">=3.99"
        self.assertEqual(updater.check_for_updates(now=1000, fetch_json=self.fetch), ["deno"])

    def test_checksum_mismatch_is_rejected(self):
        url = updater.PYPI_URL.format(name="yt-dlp")
        self.releases[url]["urls"][1]["digests"]["sha256"] = "0" * 64
        with self.assertRaises(UpdateError):
            updater.check_for_updates(now=1000, fetch_json=self.fetch)
        self.assertEqual(list(updater.PACKAGES.iterdir()), [])  # yarım ya da sahte dosya kalmadı

    def test_tampered_file_is_not_activated(self):
        updater.check_for_updates(now=1000, fetch_json=self.fetch)
        wheel = updater.PACKAGES / "yt_dlp-2026.8.19-py3-none-any.whl"
        with mock.patch.object(updater.sys, "path", []):
            self.assertEqual(updater.activate(), updater.PACKAGES / "deno-2.9.7.exe")
            self.assertIn(str(wheel), updater.sys.path)
            wheel.write_bytes(b"tampered")
            updater.sys.path.clear()
            updater.activate()
            self.assertNotIn(str(wheel), updater.sys.path)

    def test_broken_manifest(self):
        (self.folder / updater.MANIFEST_FILE).write_text("{broken", encoding="utf-8")
        self.assertIsNone(updater.activate())
        (self.folder / updater.MANIFEST_FILE).write_text('{"deno": {"file": "../../evil.exe"}}', encoding="utf-8")
        self.assertIsNone(updater.activate())


if __name__ == "__main__":
    unittest.main()
