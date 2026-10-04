import tempfile
import unittest
from pathlib import Path

from downloader import Cancelled, Download, classify_error, video_entry
from formats import download_options


class TestOptions(unittest.TestCase):
    def test_video(self):
        options = download_options("video", "1080p", "C:/Downloads", None)
        self.assertEqual(options["format"], "bv*+ba/b")
        self.assertEqual(options["format_sort"], ["res:1080", "vcodec:h264", "acodec:aac"])
        self.assertEqual(options["merge_output_format"], "mp4")
        self.assertTrue(options["windowsfilenames"])
        self.assertFalse(options["overwrites"])
        self.assertTrue(options["noplaylist"])
        self.assertNotIn("postprocessors", options)

    def test_best_video_has_no_height_limit(self):
        self.assertEqual(download_options("video", "best", "x", None)["format_sort"], ["vcodec:h264", "acodec:aac"])

    def test_audio(self):
        mp3 = download_options("audio", "mp3", "x", "C:/ffmpeg")
        self.assertEqual(mp3["postprocessors"][0], {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                                                    "preferredquality": "192"})
        self.assertEqual(mp3["ffmpeg_location"], "C:/ffmpeg")
        m4a = download_options("audio", "m4a", "x", None)
        self.assertNotIn("preferredquality", m4a["postprocessors"][0])
        self.assertNotIn("merge_output_format", m4a)


class TestErrors(unittest.TestCase):
    def test_classify(self):
        cases = [
            ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access", "private"),
            ("ERROR: [youtube] abc: Sign in to confirm your age. This video may be inappropriate", "age_restricted"),
            ("ERROR: [youtube] abc: Sign in to confirm you're not a bot", "blocked"),
            ("ERROR: [youtube] abc: The uploader has not made this video available in your country", "region_locked"),
            ("ERROR: [youtube] abc: This video is unavailable", "unavailable"),
            ("ERROR: [youtube] abc: This live stream recording is not available.", "unavailable"),
            ("ERROR: [youtube] abc: This live event will begin in 3 hours.", "live_upcoming"),
            ("ERROR: unable to download video data: HTTP Error 429: Too Many Requests", "blocked"),
            ("ERROR: Unable to download webpage: <urlopen error [Errno 11001] getaddrinfo failed>", "network"),
            ("ERROR: You have requested merging of multiple formats but ffmpeg is not installed.", "ffmpeg_missing"),
            ("[Errno 28] No space left on device", "disk_full"),
            ("Something completely different", "failed"),
        ]
        for message, code in cases:
            with self.subTest(code=code):
                self.assertEqual(classify_error(message), code)


class TestVideoEntry(unittest.TestCase):
    def test_valid(self):
        entry = video_entry({"id": "jNQXAC9IVRw", "title": "Me at the zoo", "uploader": "jawed", "duration": 19,
                             "live_status": "not_live", "extra": "ignored"})
        self.assertEqual(entry, {"id": "jNQXAC9IVRw", "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                                 "title": "Me at the zoo", "channel": "jawed", "duration": 19, "is_live": False})

    def test_untrusted_values(self):
        entry = video_entry({"id": "jNQXAC9IVRw", "title": "x" * 1000, "channel": 5, "duration": "long",
                             "live_status": "is_live", "url": "https://evil.example"})
        self.assertEqual(len(entry["title"]), 300)
        self.assertIsNone(entry["channel"])
        self.assertIsNone(entry["duration"])
        self.assertTrue(entry["is_live"])
        self.assertEqual(entry["url"], "https://www.youtube.com/watch?v=jNQXAC9IVRw")
        self.assertEqual(video_entry({"id": "jNQXAC9IVRw"})["title"], "jNQXAC9IVRw")

    def test_invalid(self):
        for raw in (None, "text", {}, {"id": "UCchannel-id-is-longer"}, {"id": 12345678901}):
            with self.subTest(raw=raw):
                self.assertIsNone(video_entry(raw))


class TestDownload(unittest.TestCase):
    def test_progress_spans_video_and_audio_parts(self):
        updates = []
        download = Download("url", {}, lambda *values: updates.append(values))
        download.parts = 2
        download._progress_hook({"status": "downloading", "filename": "a.f137.mp4", "downloaded_bytes": 50,
                                 "total_bytes": 100, "speed": 1000, "eta": 3})
        download._progress_hook({"status": "downloading", "filename": "a.f140.m4a", "downloaded_bytes": 50,
                                 "total_bytes_estimate": 100})
        download._progress_hook({"status": "downloading", "filename": "a.f140.m4a", "downloaded_bytes": 10})
        self.assertEqual([round(update[1]) for update in updates], [25, 75, 50])
        self.assertEqual(updates[0], ("downloading", 25.0, 1000, 3))

    def test_cancel_raises_from_hook(self):
        download = Download("url", {})
        download.cancel()
        with self.assertRaises(Cancelled):
            download._progress_hook({"status": "downloading", "filename": "a.mp4", "tmpfilename": "a.mp4.part"})
        self.assertEqual(download.temp_files, {"a.mp4", "a.mp4.part"})  # temizlenecekler yine de kaydedildi

    def test_final_name(self):
        audio = Download("url", download_options("audio", "mp3", "x", None))
        self.assertEqual(audio._final_name(Path("x/song.webm")), Path("x/song.mp3"))
        video = Download("url", download_options("video", "720p", "x", None))
        video.parts = 2
        self.assertEqual(video._final_name(Path("x/clip.webm")), Path("x/clip.mp4"))

    def test_clean_up_removes_partial_files(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            name = str(folder / "Song [Official Video].f137.mp4")
            leftovers = [name, name + ".part", name + ".ytdl", name + ".part-Frag1", name + ".part-Frag12"]
            for path in leftovers:
                Path(path).write_text("x")
            keep = folder / "Other video.mp4"
            keep.write_text("x")
            download = Download("url", {})
            download.temp_files = {name}
            download._clean_up()
            self.assertEqual(list(folder.iterdir()), [keep])


if __name__ == "__main__":
    unittest.main()
