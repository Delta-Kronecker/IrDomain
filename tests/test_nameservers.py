import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata.dnsinfo import nameservers


class ProviderDetectionTests(unittest.TestCase):
    def test_cloudflare(self):
        self.assertEqual(
            nameservers.detect_provider(["alice.ns.cloudflare.com", "bob.ns.cloudflare.com"]),
            "cloudflare",
        )

    def test_arvancloud(self):
        self.assertEqual(
            nameservers.detect_provider(["ns1.arvancloud.ir", "ns2.arvancloud.ir"]),
            "arvancloud",
        )

    def test_aws_by_substring(self):
        self.assertEqual(
            nameservers.detect_provider([
                "ns-123.awsdns-12.com",
                "ns-456.awsdns-34.net",
            ]),
            "aws",
        )

    def test_godaddy(self):
        self.assertEqual(
            nameservers.detect_provider(["ns1.domaincontrol.com"]),
            "godaddy",
        )

    def test_irandns(self):
        self.assertEqual(
            nameservers.detect_provider(["ns1.irandns.com"]),
            "irandns",
        )

    def test_parspack(self):
        self.assertEqual(
            nameservers.detect_provider(["ns1.parspack.co", "ns2.parspack.co"]),
            "parspack",
        )

    def test_unknown(self):
        self.assertIsNone(nameservers.detect_provider(["ns1.example-host.net"]))
        self.assertIsNone(nameservers.detect_provider([]))


if __name__ == "__main__":
    unittest.main()
