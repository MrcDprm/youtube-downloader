import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

import storage
from i18n import format_duration, format_speed
from settings import SETTINGS_FILE, clean_settings, default_settings, load_settings, save_settings
from thumbnails import MAX_BYTES, fetch_thumbnail


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def image_bytes(image_format, size=(320, 180)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "red").save(buffer, image_format)
    return buffer.getvalue()


class TestThumbnails(unittest.TestCase):
    def test_resized_to_requested_size(self):
        requested = []
        opener = lambda url, timeout: requested.append(url) or FakeResponse(image_bytes("JPEG"))
        image = fetch_thumbnail("jNQXAC9IVRw", (96, 54), opener)
        self.assertEqual(image.size, (96, 54))
        self.assertEqual(requested, ["https://i.ytimg.com/vi/jNQXAC9IVRw/mqdefault.jpg"])

    def test_failures_return_none(self):
        def offline(url, timeout):
            raise OSError("offline")

        cases = [
            ("../../etc", lambda url, timeout: FakeResponse(image_bytes("JPEG"))),
            ("jNQXAC9IVRw", offline),
            ("jNQXAC9IVRw", lambda url, timeout: FakeResponse(b"<html>not an image</html>")),
            ("jNQXAC9IVRw", lambda url, timeout: FakeResponse(image_bytes("GIF"))),
            ("jNQXAC9IVRw", lambda url, timeout: FakeResponse(b"\xff" * (MAX_BYTES + 10))),
        ]
        for video_id, opener in cases:
            with self.subTest(video_id=video_id):
                self.assertIsNone(fetch_thumbnail(video_id, (96, 54), opener))


class TestFormatting(unittest.TestCase):
    def test_duration(self):
        for seconds, expected in ((0, "0:00"), (65, "1:05"), (3725, "1:02:05"), (-5, "0:00")):
            with self.subTest(seconds=seconds):
                self.assertEqual(format_duration(seconds), expected)

    def test_speed(self):
        self.assertEqual(format_speed(2_400_000, "tr"), "2,3 MB/sn")
        self.assertEqual(format_speed(2_400_000, "en"), "2.3 MB/s")
        self.assertEqual(format_speed(512_000, "en"), "500 KB/s")


class TestSettings(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        patcher = mock.patch.object(storage, "DATA_DIR", self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_defaults_and_round_trip(self):
        self.assertEqual(load_settings(), default_settings())
        settings = {"lang": "en", "theme": "light", "format": "audio:mp3", "output_dir": "D:\\Music"}
        save_settings(settings)
        self.assertEqual(load_settings(), settings)

    def test_invalid_values_fall_back(self):
        data = {"lang": "de", "theme": None, "format": "video:8k", "output_dir": "x" * 1000}
        self.assertEqual(clean_settings(data), default_settings())
        (self.folder / SETTINGS_FILE).write_text("[1, 2", encoding="utf-8")
        self.assertEqual(load_settings(), default_settings())


if __name__ == "__main__":
    unittest.main()
