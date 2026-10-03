#!/usr/bin/env python3
"""Pure parser regressions using actual captured first-party HTML excerpts."""

from __future__ import annotations

import gzip
import hashlib
import json
import unittest
from pathlib import Path

from emmy_source import SourceError, category_results

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "emmys"


class EmmySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((FIXTURES / "sources.json").read_text(encoding="utf-8"))
        cls.fixtures = {}
        for source in manifest["fixtures"]:
            raw = gzip.decompress((FIXTURES / source["file"]).read_bytes())
            if hashlib.sha256(raw).hexdigest() != source["excerptSha256"]:
                raise AssertionError("captured excerpt fingerprint mismatch")
            cls.fixtures[source["file"].split(".")[0]] = (source, raw.decode("utf-8"))

    def parse(self, name):
        source, html = self.fixtures[name]
        return category_results(html, source["year"], source["url"])

    def test_full_programme_credits_survive_jsonld_truncation(self):
        result = self.parse("comedy-2026")
        self.assertEqual(result["nominationCount"], 8)
        self.assertEqual(result["winnerCount"], 1)
        winner = result["winners"][0]
        self.assertEqual(winner["heading"], "Widow’s Bay")
        self.assertEqual(len(winner["credits"]), 13)
        self.assertIn({"name": "Katie Dippold", "role": "Executive Producer", "url": "https://www.televisionacademy.com/bios/katie-dippold"}, winner["credits"])

    def test_host_layout_without_h3_preserves_work_and_role(self):
        result = self.parse("host-2026")
        winner = result["winners"][0]
        self.assertEqual(winner["heading"], "Jimmy Kimmel")
        self.assertEqual(winner["programmes"][0]["name"], "Who Wants To Be A Millionaire")
        self.assertEqual(winner["credits"][0]["role"], "Host")

    def test_historical_movie_does_not_inherit_jsonld_series_type(self):
        result = self.parse("movie-1949")
        winner = result["winners"][0]
        self.assertEqual(result["sourceCategory"], "Best Film Made For Television")
        self.assertEqual(winner["heading"], "The Necklace (Your Show Time Series)")
        self.assertEqual(winner["blankCreditCount"], 1)
        self.assertEqual(winner["credits"][0]["name"], "Stanley Rubin")
        self.assertNotIn("mediaType", winner)

    def test_juried_programme_evidence(self):
        result = self.parse("merit-2026")
        self.assertEqual(result["nominationCount"], 2)
        self.assertEqual(result["winners"][0]["heading"], "The Librarians")
        self.assertEqual(len(result["winners"][0]["credits"]), 5)

    def test_jsonld_omission_requires_agreement_between_html_views(self):
        result = self.parse("structured-reality-2022")
        self.assertEqual(result["structuredListCounts"], [4])
        self.assertEqual(result["nominationCount"], 5)
        self.assertEqual(result["nominationGridCount"], 5)
        self.assertEqual(result["winnerGridCount"], 1)
        self.assertEqual(result["winners"][0]["heading"], "Queer Eye")
        self.assertEqual(len(result["sourceDiagnostics"]), 1)

    def test_contradictory_grid_winner_marker_fails_closed(self):
        source, html = self.fixtures["structured-reality-2022"]
        with self.assertRaises(SourceError):
            category_results(html.replace("nomination-status--winner", "nomination-status--nominee"), source["year"], source["url"])

    def test_multiple_winners_and_identical_nonwinning_source_blocks(self):
        result = self.parse("drama-directing-1990")
        self.assertEqual(result["nominationCount"], 5)
        self.assertEqual(result["nominationGridCount"], 5)
        self.assertEqual(result["winnerCount"], 2)
        self.assertEqual(result["winnerGridCount"], 2)
        self.assertEqual([w["heading"] for w in result["winners"]], ["Equal Justice", "Thirtysomething"])
        self.assertTrue(any("non-winning" in d for d in result["sourceDiagnostics"]))
        # These source blocks omit both directors; parser evidence must not invent them.
        self.assertEqual([w["credits"] for w in result["winners"]], [[], []])

    def test_awarded_episode_and_programme_remain_distinct_source_evidence(self):
        winner = self.parse("comedy-directing-2026")["winners"][0]
        self.assertEqual(winner["programmes"][0]["name"], "Widow’s Bay")
        self.assertEqual(winner["sourceDetailLines"], ["Welcome To Widow's Bay!", "Apple TV"])
        self.assertEqual(winner["credits"][0]["name"], "Hiro Murai")
        self.assertEqual(winner["credits"][0]["role"], "Directed by")

    def test_wrong_ceremony_fails_closed(self):
        source, html = self.fixtures["movie-1949"]
        with self.assertRaises(SourceError):
            category_results(html, 1950, source["url"])

    def test_missing_winner_marker_is_not_a_no_award(self):
        source, html = self.fixtures["merit-2026"]
        with self.assertRaises(SourceError):
            category_results(html.replace("nomination--winner", "nomination--nominee"), source["year"], source["url"])

    def test_ambiguous_winner_state_fails_closed(self):
        source, html = self.fixtures["merit-2026"]
        with self.assertRaises(SourceError):
            category_results(html.replace("nomination--winner", "nomination--winner nomination--nominee"), source["year"], source["url"])

    def test_source_keys_ignore_display_position(self):
        source, html = self.fixtures["host-2026"]
        original = category_results(html, source["year"], source["url"])
        shifted = category_results(html.replace("mainDisplayItem ===", "changedDisplayPosition ==="), source["year"], source["url"])
        self.assertEqual(original["winners"], shifted["winners"])


if __name__ == "__main__":
    unittest.main()
