import unittest

from links import LinkError, canonical_url, parse_link

VIDEO = "jNQXAC9IVRw"
PLAYLIST = "PL6B3937A5D230E335"


class TestParseLink(unittest.TestCase):
    def test_video_links(self):
        links = [
            f"https://www.youtube.com/watch?v={VIDEO}",
            f"https://youtube.com/watch?v={VIDEO}&t=42s",
            f"http://m.youtube.com/watch?feature=share&v={VIDEO}",
            f"https://music.youtube.com/watch?v={VIDEO}",
            f"https://youtu.be/{VIDEO}?si=abc",
            f"youtu.be/{VIDEO}",
            f"www.youtube.com/watch?v={VIDEO}",
            f"https://www.youtube.com/shorts/{VIDEO}",
            f"https://www.youtube.com/live/{VIDEO}",
            f"https://www.youtube.com/embed/{VIDEO}",
            f"  https://WWW.YouTube.com/watch?v={VIDEO}  ",
            f"https://www.youtube.com/watch?v={VIDEO}&list={PLAYLIST}",  # listedeki video: sadece video
        ]
        for link in links:
            with self.subTest(link=link):
                self.assertEqual(parse_link(link), ("video", VIDEO))

    def test_playlist_links(self):
        for link in (f"https://www.youtube.com/playlist?list={PLAYLIST}", f"youtube.com/playlist?list={PLAYLIST}&si=x"):
            with self.subTest(link=link):
                self.assertEqual(parse_link(link), ("playlist", PLAYLIST))

    def test_rejected_links(self):
        cases = [
            ("", "empty"),
            ("   ", "empty"),
            ("https://vimeo.com/123", "not_youtube"),
            (f"https://youtube.com.evil.example/watch?v={VIDEO}", "not_youtube"),
            (f"https://evil.example/?u=youtube.com/watch?v={VIDEO}", "not_youtube"),
            (f"ftp://youtube.com/watch?v={VIDEO}", "not_youtube"),
            (f"file:///C:/youtube.com/watch?v={VIDEO}", "not_youtube"),
            ("https://www.youtube.com/" + "a" * 600, "not_youtube"),
            ("https://www.youtube.com/@channel", "unsupported"),
            ("https://www.youtube.com/watch?v=short", "unsupported"),
            ("https://www.youtube.com/watch?v=abc$%^&*()_", "unsupported"),
            ("https://youtu.be/", "unsupported"),
            ("https://www.youtube.com/playlist?list=x", "unsupported"),
            ("hello world", "not_youtube"),
        ]
        for text, code in cases:
            with self.subTest(text=text[:60]):
                with self.assertRaises(LinkError) as context:
                    parse_link(text)
                self.assertEqual(context.exception.code, code)

    def test_canonical_url(self):
        self.assertEqual(canonical_url("video", VIDEO), f"https://www.youtube.com/watch?v={VIDEO}")
        self.assertEqual(canonical_url("playlist", PLAYLIST), f"https://www.youtube.com/playlist?list={PLAYLIST}")


if __name__ == "__main__":
    unittest.main()
