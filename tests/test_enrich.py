import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata.enrich import asn, whois

TSV = """\
1.0.0.0\t1.0.0.255\t13335\tAU\tCloudflare
17.0.0.0\t17.255.255.255\t714\tUS\tApple
20.0.0.0\t20.0.3.255\t8075\tIR\tMCI
"""


class AsnDbTests(unittest.TestCase):
    def setUp(self):
        self.db = asn.AsnDB.from_tsv_text(TSV)

    def test_lookup_hit(self):
        rec = self.db.lookup("20.0.1.5")
        self.assertEqual(rec["asn"], "8075")
        self.assertEqual(rec["country"], "IR")

    def test_lookup_miss(self):
        self.assertIsNone(self.db.lookup("9.9.9.9"))

    def test_lookup_zero_asn_skipped(self):
        db = asn.AsnDB.from_tsv_text("5.5.5.0\t5.5.5.255\t0\tZZ\tNone\n")
        self.assertIsNone(db.lookup("5.5.5.1"))


class WhoisParseTests(unittest.TestCase):
    def test_parse_ir_style(self):
        text = "domain: EXAMPLE.IR\ncountry: IR\nregistrar: Server.ir\n"
        info = whois.parse_whois_text(text)
        self.assertEqual(info["registrant_country"], "IR")
        self.assertEqual(info["registrar"], "Server.ir")

    def test_parse_generic_style(self):
        text = "Domain Name: EXAMPLE.COM\nRegistrant Country: US\nRegistrar: ExampleReg\n"
        info = whois.parse_whois_text(text)
        self.assertEqual(info["registrant_country"], "US")
        self.assertEqual(info["registrar"], "ExampleReg")


if __name__ == "__main__":
    unittest.main()
