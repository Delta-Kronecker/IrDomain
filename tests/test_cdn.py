import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata.cdn import detect


class CnameMatchTests(unittest.TestCase):
    def test_cloudfront(self):
        hit = detect.match_cname(["d111.cloudfront.net"])
        self.assertEqual(hit[0], "cloudfront")

    def test_cloudflare_proxied(self):
        hit = detect.match_cname(["site.cdn.cloudflare.net"])
        self.assertEqual(hit[0], "cloudflare")

    def test_akamai_edgekey(self):
        hit = detect.match_cname(["www.example.edgekey.net"])
        self.assertEqual(hit[0], "akamai")

    def test_arvancloud(self):
        hit = detect.match_cname(["x.arvancloud.ir"])
        self.assertEqual(hit[0], "arvancloud")

    def test_no_match(self):
        self.assertIsNone(detect.match_cname(["host.example.com"]))


class HeaderMatchTests(unittest.TestCase):
    def test_cloudflare_headers(self):
        hit = detect.match_headers({"CF-RAY": "8f1a2b-LHR", "Server": "cloudflare"})
        self.assertEqual(hit[0], "cloudflare")

    def test_fastly_headers(self):
        headers = {
            "X-Served-By": "cache-lhr-123, cache-lhr-1",
            "Via": "1.1 varnish",
        }
        hit = detect.match_headers(headers)
        self.assertEqual(hit[0], "fastly")

    def test_akamai_headers(self):
        hit = detect.match_headers({"Server": "AkamaiGHost", "X-Akamai-Transformed": "9"})
        self.assertEqual(hit[0], "akamai")

    def test_no_headers(self):
        self.assertIsNone(detect.match_headers({}))


class DetectTests(unittest.TestCase):
    def test_high_from_cname(self):
        row = detect.detect(["d1.cloudfront.net"], {}, None)
        self.assertEqual(row["cdn"], "cloudfront")
        self.assertEqual(row["confidence"], "high")

    def test_low_from_asn_only(self):
        row = detect.detect([], {}, "13335")
        self.assertEqual(row["cdn"], "cloudflare")
        self.assertEqual(row["confidence"], "low")

    def test_corroborated(self):
        row = detect.detect(["site.cdn.cloudflare.net"], {"CF-RAY": "x"}, "13335")
        self.assertEqual(row["confidence"], "high")
        self.assertIn("corroborated", row["signals"])

    def test_none(self):
        row = detect.detect([], {"Server": "nginx"}, "1234")
        self.assertEqual(row["cdn"], "none")
        self.assertEqual(row["confidence"], "none")


if __name__ == "__main__":
    unittest.main()
