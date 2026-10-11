import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata.classify import features, scorer


class FeatureTests(unittest.TestCase):
    def test_persian_ratio(self):
        self.assertAlmostEqual(features.persian_ratio("سلام دنیا"), 1.0)
        self.assertAlmostEqual(features.persian_ratio("hello world"), 0.0)
        mixed = features.persian_ratio("hello سلام")
        self.assertGreater(mixed, 0.0)
        self.assertLess(mixed, 1.0)

    def test_strip_html_removes_script(self):
        html = "<style>b{}</style><script>var x='سلام';</script><p>تست</p>"
        text = features.strip_html(html)
        self.assertNotIn("var x", text)
        self.assertIn("تست", text)

    def test_lang_detection(self):
        self.assertEqual(features.detect_lang('<html lang="fa-IR">'), "fa-ir")
        self.assertEqual(features.detect_lang("<html>"), "")

    def test_token_hits(self):
        hits = features.token_hits('<div>زرین‌پال +989121234567</div>')
        self.assertTrue(any(h.startswith("strong:") for h in hits))

    def test_html_entities_decoded(self):
        feats = features.extract("<title>&#1583;&#1587;&#1578; &#1575;&#1587;&#1578;</title>")
        self.assertGreater(feats["persian_ratio"], 0.5)

    def test_parked_detection_english(self):
        self.assertTrue(features.parked("<h1>Domain For Sale</h1>"))
        self.assertTrue(features.parked("<p>Buy this domain today</p>"))
        self.assertFalse(features.parked("<p>فروشگاه اینترنتی</p>"))

    def test_parked_detection_persian(self):
        self.assertTrue(features.parked("<p>این دامنه برای فروش است</p>"))

    def test_extract_marks_parked(self):
        feats = features.extract("<html><body>Domain Parking</body></html>")
        self.assertTrue(feats["parked"])


class ScorerTests(unittest.TestCase):
    def test_iranian_page(self):
        feats = {
            "persian_ratio": 0.9,
            "lang": "fa",
            "token_hits": ["strong:zarinpal", "strong:phone_ir", "weak:تهران"],
        }
        value, verdict = scorer.score(feats)
        self.assertEqual(verdict, "iranian")
        self.assertGreaterEqual(value, 0.6)

    def test_foreign_page(self):
        feats = {"persian_ratio": 0.0, "lang": "en", "token_hits": []}
        _, verdict = scorer.score(feats)
        self.assertEqual(verdict, "foreign")

    def test_uncertain_page(self):
        feats = {"persian_ratio": 0.15, "lang": "fa", "token_hits": ["weak:ایران"]}
        _, verdict = scorer.score(feats)
        self.assertEqual(verdict, "uncertain")

    def test_parked_page_is_junk(self):
        feats = {
            "persian_ratio": 0.9,
            "lang": "fa",
            "token_hits": ["strong:phone_ir"],
            "parked": True,
        }
        value, verdict = scorer.score(feats)
        self.assertEqual(verdict, "junk")
        self.assertEqual(value, 0.0)


if __name__ == "__main__":
    unittest.main()
