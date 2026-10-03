#!/usr/bin/env python3
"""Pure parser regressions using actual captured first-party HTML excerpts."""

from __future__ import annotations

import gzip
import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from emmy_source import SourceError, category_results
from fetch_emmy_snapshot import SOURCE_DIR, apply_no_award_evidence, candidate_pages, category_for_winner, category_for_year, load, no_award_exceptions, review_for_year
from validate_emmy_source import validate_review

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

    def test_actual_1969_absent_markers_need_the_independent_history_notice(self):
        source, html = self.fixtures["supporting-performance-1969"]
        with self.assertRaises(SourceError) as caught:
            category_results(html, source["year"], source["url"])
        rejected = caught.exception.details
        self.assertEqual(rejected["nominationCount"], 3)
        self.assertEqual([n["heading"] for n in rejected["nominations"]], ["Ned Glass", "Billy Schulman", "Hal Holbrook"])
        notice = no_award_exceptions(load(SOURCE_DIR / "lineage-decisions.json"))[source["url"]]
        page = {"year": source["year"], "sourceUrl": source["url"], **rejected, "winnerCount": 0, "winners": []}
        reconciled = apply_no_award_evidence(page, notice)
        self.assertEqual(reconciled["outcome"], "no-award")
        self.assertEqual(reconciled["nominations"], rejected["nominations"])

    def test_actual_1969_variety_winner_conflict_cannot_be_silently_reconciled(self):
        source, _ = self.fixtures["variety-directing-1969"]
        page = self.parse("variety-directing-1969")
        self.assertEqual(page["winners"][0]["heading"], "The Dean Martin Show")
        notice = no_award_exceptions(load(SOURCE_DIR / "lineage-decisions.json"))[source["url"]]
        with self.assertRaises(SourceError) as caught:
            apply_no_award_evidence(page, notice)
        self.assertEqual(caught.exception.conflicting_winner_evidence["html"], page)
        self.assertEqual(caught.exception.conflicting_winner_evidence["independentNoAward"], notice)

    def test_no_award_notice_cannot_be_applied_to_a_different_event_year(self):
        ledger = deepcopy(load(SOURCE_DIR / "lineage-decisions.json"))
        notice = next(e for e in ledger["annualExceptions"] if e["year"] == 2007)
        notice["year"] = 2009  # Migrated page date; the actual release body says 2007.
        with self.assertRaises(SourceError):
            no_award_exceptions(ledger)


class EmmyLineageReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        cls.decisions = {d["sourceSlug"]: d for p in ledger["programmes"] for d in p["decisions"]}

    def test_miniseries_slug_does_not_reclassify_the_1973_single_programme(self):
        decision = self.decisions["outstanding-miniseries"]
        self.assertEqual(category_for_year(decision, 1973), "television-movie")
        self.assertEqual(category_for_year(decision, 1974), "limited-or-anthology-series")

    def test_merged_programme_period_uses_the_awarded_production_format(self):
        decision = self.decisions["outstanding-miniseries-or-movie"]
        self.assertEqual(category_for_year(decision, 1990), "television-movie")
        self.assertIsNone(category_for_year(decision, 1991))
        self.assertEqual(category_for_year(decision, 1992), "limited-or-anthology-series")
        self.assertEqual(category_for_year(decision, 2011), "limited-or-anthology-series")
        for year in (2012, 2013):
            self.assertEqual(category_for_year(decision, year), "television-movie")
        self.assertIsNone(category_for_year(decision, 1991))

    def test_reality_split_does_not_allocate_the_whole_older_field_to_one_successor(self):
        decision = self.decisions["outstanding-reality-program"]
        for year in (2004, 2005, 2006, 2012, 2013):
            self.assertEqual(category_for_year(decision, year), "structured-reality-program")
        for year in (2001, 2002, 2007, 2008, 2009, 2011):
            self.assertEqual(category_for_year(decision, year), "unstructured-reality-program")
        self.assertIsNone(category_for_year(decision, 2010))

    def test_single_appearance_label_does_not_turn_miniseries_into_ongoing_drama(self):
        actor = self.decisions["outstanding-lead-actor-for-a-single-appearance-in-a-drama-or-comedy-series"]
        actress = self.decisions["outstanding-lead-actress-for-a-single-appearance-in-a-drama-or-comedy-series"]
        for year in (1976, 1977):
            self.assertEqual(category_for_year(actor, year), "lead-actor-in-a-limited-or-anthology-series-or-movie")
        self.assertEqual(category_for_year(actress, 1976), "lead-actress-in-a-limited-or-anthology-series-or-movie")
        # Format evidence for these miniseries cannot settle guest/continuing
        # relationships for Lou Grant, The Waltons or The Rockford Files.
        self.assertIsNone(category_for_year(actor, 1978))
        for year in (1977, 1978):
            self.assertIsNone(category_for_year(actress, year))

    def test_character_description_does_not_rewrite_the_original_lead_award(self):
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        lead_slug = "outstanding-lead-actor-for-a-single-appearance-in-a-drama-or-comedy-series"
        support_slug = "outstanding-single-performance-by-a-supporting-actor-in-a-comedy-or-drama-series"
        page = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith('/1976/' + lead_slug))
        self.assertIn("Lead Actor", page["sourceCategory"])
        self.assertEqual(page["winners"][0]["heading"], "Edward Asner")
        self.assertEqual(category_for_winner(self.decisions[lead_slug], 1976, page["winners"][0]["sourceKey"]),
                         "lead-actor-in-a-limited-or-anthology-series-or-movie")
        self.assertEqual(category_for_year(self.decisions[support_slug], 1977),
                         "supporting-actor-in-a-limited-or-anthology-series-or-movie")
        # Asner's separate Roots supporting award cannot reclassify the earlier
        # explicitly headed Rich Man, Poor Man lead award, or other winners.
        self.assertEqual(category_for_year(self.decisions[support_slug], 1976),
                         "supporting-actor-in-a-limited-or-anthology-series-or-movie")
        self.assertIsNone(category_for_year(self.decisions[support_slug], 1978))

    def test_single_performance_uses_original_year_programme_eligibility(self):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        contexts = {s["url"]: s["context"] for s in ledger["contextSources"]}
        base = "https://www.televisionacademy.com/awards/nominees-winners/"
        self.assertIn("Nominee Columbo NBC Sunday Mystery Movie", contexts[base + "1975/outstanding-miniseries"])
        self.assertIn("Nominee Columbo NBC Sunday Mystery Movie", contexts[base + "1976/outstanding-drama-series"])
        self.assertIn("Winner Upstairs, Downstairs Masterpiece Theatre", contexts[base + "1975/outstanding-drama-series"])
        self.assertIn("Winner Upstairs, Downstairs Masterpiece Theatre", contexts[base + "1976/outstanding-miniseries"])
        decision = self.decisions["outstanding-single-performance-by-a-supporting-actor-in-a-comedy-or-drama-series"]
        for year in (1975, 1976):
            review = review_for_year(decision, year)
            self.assertIn(base + f"{year}/outstanding-miniseries", review["externalEvidence"])
            self.assertEqual(category_for_year(decision, year),
                             "supporting-actor-in-a-limited-or-anthology-series-or-movie")
        # Another season's ongoing-series eligibility must not override the
        # original limited-series performance, or resolve the disputed 1978 work.
        self.assertIsNone(category_for_year(decision, 1978))

    def test_classical_music_slug_retains_its_actual_music_series_predecessor(self):
        slug = "outstanding-classical-music-dance-program"
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1956/' + slug))
        self.assertEqual(page["sourceCategory"], "Best Music Series")
        self.assertEqual(page["winners"][0]["heading"], "Your Hit Parade")
        self.assertEqual(category_for_winner(self.decisions[slug], 1956, page["winners"][0]["sourceKey"]),
                         "variety-series")

    def test_original_western_and_mystery_fields_are_programme_drama_branches(self):
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        for slug, years, work in (("best-western-series", (1959,), "Maverick"),
                                  ("best-mystery-action-or-adventure-program", (1954, 1953), "Dragnet"),
                                  ("best-mystery-or-intrigue-series", (1955,), "Dragnet")):
            for year in years:
                page = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith(f'/{year}/' + slug))
                self.assertEqual([w["heading"] for w in page["winners"]], [work])
                self.assertEqual(category_for_year(self.decisions[slug], year), "drama-series")
        # An Action/Adventure label alone cannot establish the mixed-format
        # Disneyland programme's predecessor under Drama or Variety.
        self.assertIsNone(category_for_year(self.decisions["best-action-or-adventure-series"], 1956))

    def test_one_supporting_slug_preserves_its_special_and_series_headings(self):
        slug = "outstanding-single-performance-by-a-supporting-actress"
        decision = self.decisions[slug]
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        pages = {p["year"]: p for p in snapshot["pages"] if p["sourceUrl"].endswith('/' + slug)}
        self.assertIn("Special", pages[1975]["sourceCategory"])
        self.assertIn("Series", pages[1976]["sourceCategory"])
        for year in pages:
            self.assertEqual(category_for_year(decision, year),
                             "supporting-actress-in-a-limited-or-anthology-series-or-movie")
        # The original special/series distinction must survive allocation to a
        # combined modern category; the common URL must not overwrite it.
        self.assertNotEqual(review_for_year(decision, 1975)["reviewedSourceHeadings"],
                            review_for_year(decision, 1976)["reviewedSourceHeadings"])

    def test_scope_exclusion_retains_reviewed_facts_without_publishing_them(self):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        indices = load(SOURCE_DIR / "annual-indices.json")
        requested = {p["url"] for p in candidate_pages(indices["years"], ledger)}
        slug = "best-single-program-of-the-year"
        decision = self.decisions[slug]
        for page in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]:
            if page["sourceUrl"].endswith('/' + slug):
                self.assertIn(page["sourceUrl"], requested)
                for winner in page["winners"]:
                    self.assertIsNone(category_for_winner(decision, page["year"], winner["sourceKey"]))
        # Unreviewed, out-of-scope craft fields are still not acquired merely
        # because the authority exposes them in an annual index.
        self.assertFalse(any(url.endswith('/outstanding-main-title-design') for url in requested))

    def test_excluded_evidence_still_rejects_changed_hashes_and_category_targets(self):
        slug = "best-live-show"
        decision = deepcopy(self.decisions[slug])
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/' + slug))
        arguments = ({page["year"]: page["sourceUrl"]},
                     {page["sourceUrl"]: (page["year"], slug)}, {page["sourceUrl"]: page},
                     {"variety-special-live"})
        validate_review(decision, *arguments)
        decision["reviewedSourcePages"][0]["sha256"] = "0" * 64
        with self.assertRaises(SourceError):
            validate_review(decision, *arguments)
        decision = deepcopy(self.decisions[slug])
        decision["currentCategory"] = "variety-special-live"
        with self.assertRaises(SourceError):
            validate_review(decision, *arguments)

    def test_later_reality_nomination_is_context_and_not_an_extra_historical_winner(self):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        context = next(s for s in ledger["contextSources"] if s["url"].endswith("/2014/outstanding-structured-reality-program"))
        self.assertIn("Nominee Undercover Boss", context["context"])
        review = review_for_year(self.decisions["outstanding-reality-program"], 2012)
        self.assertEqual(review["years"], [2013, 2012])
        self.assertEqual(len(review["reviewedSourcePages"]), 2)
        self.assertEqual(sum(len(p["winnerSourceKeys"]) for p in review["reviewedSourcePages"]), 2)

    def test_restored_hosted_field_does_not_reclassify_the_older_informational_archive(self):
        for slug, target in (("outstanding-informational-series", "documentary-or-nonfiction-series"),
                             ("outstanding-informational-special", "documentary-or-nonfiction-special")):
            self.assertEqual(category_for_year(self.decisions[slug], 2002), target)
            self.assertIsNone(category_for_year(self.decisions[slug], 1994))

    def test_variety_special_slug_does_not_turn_the_1968_series_into_a_live_special(self):
        decision = self.decisions["outstanding-variety-music-or-comedy-special"]
        self.assertEqual(category_for_year(decision, 1968), "variety-series")
        self.assertIsNone(category_for_year(decision, 2017))
        self.assertEqual(category_for_year(decision, 2018), "variety-special-live")

    def test_period_context_reference_requires_pinned_evidence(self):
        decision = self.decisions["outstanding-miniseries-or-movie"]
        review = deepcopy(review_for_year(decision, 2012))
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        page = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith("/2012/outstanding-miniseries-or-movie"))
        arguments = (review, {2012: page["sourceUrl"]}, {page["sourceUrl"]: (2012, decision["sourceSlug"])},
                     {page["sourceUrl"]: page}, {"television-movie"})
        contexts = {s["url"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        validate_review(*arguments, contexts)
        review["externalEvidence"] = ["https://www.televisionacademy.com/unreviewed-context"]
        with self.assertRaises(SourceError):
            validate_review(*arguments, contexts)

    def test_under_one_hour_animation_is_not_the_later_short_form_award(self):
        decision = self.decisions["outstanding-short-format-animated-program"]
        self.assertEqual(category_for_year(decision, 2009), "animated-program")
        self.assertIsNone(category_for_year(decision, 2010))

    def test_variety_merger_keeps_both_programme_branches(self):
        for slug in ("outstanding-variety-series-talk", "outstanding-variety-sketch-series"):
            self.assertEqual(category_for_year(self.decisions[slug], 2024), "variety-series")

    def test_pre_split_voice_over_uses_exact_role_not_documentary_title(self):
        decision = self.decisions["outstanding-voice-over-performance"]
        # Madeline's fictional narrator and the named historical character voices
        # remain character performances; the nonfiction Narrator role is distinct.
        for year in (1994, 1997, 2000):
            self.assertEqual(category_for_year(decision, year), "character-voice-over-performance")
        for year in (2005, 2008, 2013):
            self.assertEqual(category_for_year(decision, year), "narrator")

    def test_undivided_variety_directing_is_not_assumed_to_be_series(self):
        decision = self.decisions["outstanding-directing-for-a-variety-series"]
        self.assertEqual(category_for_year(decision, 1996), "directing-for-a-variety-special")
        self.assertEqual(category_for_year(decision, 1991), "directing-for-a-variety-series")
        self.assertIsNone(category_for_year(decision, 1971))
        self.assertEqual(category_for_year(decision, 2009), "directing-for-a-variety-series")

    def test_mixed_1990_writing_winners_are_allocated_once_to_their_actual_formats(self):
        decision = self.decisions["outstanding-writing-for-a-variety-series"]
        self.assertIsNone(category_for_year(decision, 1990))
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith("/1990/outstanding-writing-for-a-variety-series"))
        targets = {w["heading"]: category_for_winner(decision, 1990, w["sourceKey"]) for w in page["winners"]}
        self.assertEqual(targets, {"Billy Crystal: Midnight Train to Moscow": "writing-for-a-variety-special",
                                  "The Tracey Ullman Show": "writing-for-a-variety-series"})

    def test_combined_1961_supporting_field_keeps_both_winners_and_genres(self):
        decision = self.decisions["outstanding-performance-in-a-supporting-role-by-an-actor-or-actress-in-a-series"]
        allocations = review_for_year(decision, 1961)["winnerAllocations"]
        self.assertEqual([category_for_winner(decision, 1961, a["sourceKey"]) for a in allocations],
                         ["supporting-actor-in-a-drama-series", "supporting-actor-in-a-comedy-series"])

    def test_incomplete_mixed_allocation_fails_validation(self):
        decision = self.decisions["outstanding-writing-for-a-variety-series"]
        review = deepcopy(review_for_year(decision, 1990))
        review["winnerAllocations"].pop()
        pages = {p["sourceUrl"]: p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                 if p["year"] in review["years"] and p["sourceUrl"].endswith('/' + decision["sourceSlug"])}
        with self.assertRaises(SourceError):
            validate_review(review, {p["year"]: u for u, p in pages.items()},
                            {u: (p["year"], decision["sourceSlug"]) for u, p in pages.items()}, pages,
                            {"writing-for-a-variety-series", "writing-for-a-variety-special"})

    def test_mixed_winner_key_cannot_be_applied_to_another_ceremony(self):
        decision = self.decisions["outstanding-writing-for-a-variety-series"]
        allocation = next(a for a in review_for_year(decision, 1990)["winnerAllocations"] if a["year"] == 1974)
        with self.assertRaises(SourceError):
            category_for_winner(decision, 1990, allocation["sourceKey"])

    def test_current_game_show_contract_does_not_extend_into_the_separate_daytime_history(self):
        decision = self.decisions["outstanding-game-show"]
        self.assertIsNone(category_for_year(decision, 2022))
        self.assertEqual(category_for_year(decision, 2023), "game-show")

    def test_early_quiz_field_does_not_classify_every_audience_participation_show_as_a_game(self):
        decision = self.decisions["best-audience-participation-quiz-or-panel-program"]
        for year in (1951, 1953, 1956, 1959):
            self.assertEqual(category_for_year(decision, year), "game-show")
        for year in (1954, 1955):
            self.assertIsNone(category_for_year(decision, year))
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1954/' + decision["sourceSlug"]))
        self.assertEqual({w["heading"] for w in page["winners"]}, {"What's My Line?", "This Is Your Life"})
        # A recognisable game show in the tie is not enough to accept a mixed
        # page while the other winner's predecessor remains unresolved.
        for winner in page["winners"]:
            self.assertIsNone(category_for_winner(decision, 1954, winner["sourceKey"]))

    def test_duration_branches_follow_the_actual_awarded_programme(self):
        decision = self.decisions["best-direction-half-hour-or-less"]
        self.assertEqual(category_for_year(decision, 1957), "directing-for-a-comedy-series")
        self.assertEqual(category_for_year(decision, 1958), "directing-for-a-drama-series")
        decision = self.decisions["best-direction-one-hour-or-more"]
        self.assertEqual(category_for_year(decision, 1957), "directing-for-a-drama-series")
        self.assertEqual(category_for_year(decision, 1958), "directing-for-a-variety-series")

    def test_combined_guest_performer_branches_preserve_the_reviewed_recipients(self):
        decision = self.decisions["outstanding-guest-performer-in-a-comedy-series"]
        self.assertEqual(category_for_year(decision, 1987), "guest-actor-in-a-comedy-series")
        self.assertEqual(category_for_year(decision, 1988), "guest-actress-in-a-comedy-series")

    def test_drama_writing_split_keeps_series_and_special_programmes_separate(self):
        decision = self.decisions["outstanding-writing-achievement-in-drama-adaptation"]
        self.assertEqual(category_for_year(decision, 1964), "writing-for-a-drama-series")
        self.assertEqual(category_for_year(decision, 1974), "writing-for-a-limited-or-anthology-series-or-movie")

    def test_overlapping_review_periods_fail_closed(self):
        decision = deepcopy(self.decisions["outstanding-miniseries"])
        decision["periods"][0]["years"].append(1973)
        with self.assertRaises(SourceError):
            review_for_year(decision, 1973)

    def test_changed_source_bytes_invalidate_the_accepted_allocation(self):
        decision = deepcopy(self.decisions["outstanding-movie"])
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        page = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith("/2026/outstanding-movie"))
        decision["reviewedSourcePages"][0]["sha256"] = "0" * 64
        with self.assertRaises(SourceError):
            validate_review(decision, {2026: page["sourceUrl"]}, {page["sourceUrl"]: (2026, "outstanding-movie")},
                {page["sourceUrl"]: page}, {"television-movie"})


if __name__ == "__main__":
    unittest.main()
