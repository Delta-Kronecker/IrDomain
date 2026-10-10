import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata.utils.domain import (
    domain_from_url,
    normalize_domain,
    registrable_domain,
)


class NormalizeTests(unittest.TestCase):
    def test_strips_scheme_path_and_www(self):
        self.assertEqual(normalize_domain("https://WWW.Aparat.com/path?a=1"), "www.aparat.com")

    def test_strips_wildcard_and_port(self):
        self.assertEqual(normalize_domain("*.blog.ir:8080"), "blog.ir")

    def test_rejects_single_label(self):
        self.assertIsNone(normalize_domain("localhost"))

    def test_rejects_bad_labels(self):
        self.assertIsNone(normalize_domain("-bad.com"))
        self.assertIsNone(normalize_domain("foo.c0m"))

    def test_registrable_second_level_ir(self):
        self.assertEqual(registrable_domain("www.example.co.ir"), "example.co.ir")
        self.assertEqual(registrable_domain("mail.example.ir"), "example.ir")
        self.assertEqual(registrable_domain("sub.aparat.com"), "aparat.com")

    def test_domain_from_url(self):
        self.assertEqual(domain_from_url("https://news.example.ir/fa/page"), "example.ir")
        self.assertIsNone(domain_from_url("not a url"))


if __name__ == "__main__":
    unittest.main()
