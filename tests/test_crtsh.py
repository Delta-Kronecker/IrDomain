import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata.collectors import crtsh


class MergeSeedsTests(unittest.TestCase):
    def test_db_seeds_first_then_new_domains(self):
        results = {"tranco": {"b.com", "a.com"}, "lists": {"c.com"}}
        seeds = crtsh.merge_seeds(["z.com"], results)
        self.assertEqual(seeds[0], "z.com")
        self.assertEqual(sorted(seeds[1:]), ["a.com", "b.com", "c.com"])

    def test_deduplicates_overlap(self):
        results = {"tranco": {"a.com"}}
        seeds = crtsh.merge_seeds(["a.com"], results)
        self.assertEqual(seeds, ["a.com"])

    def test_empty_results(self):
        self.assertEqual(crtsh.merge_seeds(["a.com"], {}), ["a.com"])


if __name__ == "__main__":
    unittest.main()
