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
from validate_emmy_source import evidence, source_url, validate_review

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


class EmmySourceAuthorityTests(unittest.TestCase):
    def test_foundation_interviews_are_context_only(self):
        url = "https://interviews.televisionacademy.com/interviews/rita-moreno"
        source_url(url, context=True)
        with self.assertRaises(SourceError):
            source_url(url)

    def test_broadcaster_production_context_cannot_supply_award_facts(self):
        contexts = load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
        pbs = [s for s in contexts if s["url"].startswith("https://www.pbs.org/")]
        self.assertTrue(pbs)
        for value in pbs:
            with self.subTest(url=value["url"]):
                evidence(value, value["url"], context=True)
                with self.assertRaises(SourceError):
                    evidence(value, value["url"])

    def test_broadcaster_context_is_limited_to_the_reviewed_production_archive(self):
        for url in ("https://www.pbs.org/awards/nominees-winners/1988",
                    "https://www.pbs.org/food/stories/example",
                    "https://www.pbs.org/wnet/americanmasters",
                    "https://www.pbs.org/wnet/americanmasters/../../food/stories/example",
                    "https://www.pbs.org/wnet/americanmasters/%2e%2e/food/stories/example",
                    "https://www.pbs.org.example.org/wnet/americanmasters/series/",
                    "https://user@www.pbs.org/wnet/americanmasters/series/",
                    "https://www.pbs.org:443/wnet/americanmasters/series/",
                    "http://www.pbs.org/wnet/americanmasters/series/"):
            with self.subTest(url=url), self.assertRaises(SourceError):
                source_url(url, context=True)

    def test_broadcaster_response_redirect_cannot_escape_the_reviewed_archive(self):
        value = deepcopy(next(s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                              if s["url"] == "https://www.pbs.org/wnet/americanmasters/series/"))
        for redirected in ("https://www.pbs.org/awards/1988", "https://example.org/series/"):
            value["resolvedUrl"] = redirected
            with self.subTest(redirected=redirected), self.assertRaises(SourceError):
                evidence(value, value["url"], context=True)

    def test_original_producer_archive_cannot_supply_award_facts(self):
        contexts = load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
        producer = [s for s in contexts if s["url"].startswith("https://billmoyers.com/")]
        self.assertEqual(len(producer), 4)
        for value in producer:
            with self.subTest(url=value["url"]):
                evidence(value, value["url"], context=True)
                with self.assertRaises(SourceError):
                    evidence(value, value["url"])

    def test_producer_context_is_limited_to_the_four_reviewed_records(self):
        for url in ("https://billmoyers.com/awards/nominees-winners/1993",
                    "https://billmoyers.com/series/unreviewed/",
                    "https://billmoyers.com/timeline/",
                    "https://billmoyers.com/series/creativity",
                    "https://billmoyers.com/series/creativity/../../awards/",
                    "https://billmoyers.com/series/%63reativity/",
                    "https://billmoyers.com/series/creativity/?award=1993",
                    "https://billmoyers.com/series/creativity/#awards",
                    "https://billmoyers.com.example.org/series/creativity/",
                    "https://user@billmoyers.com/series/creativity/",
                    "https://billmoyers.com:443/series/creativity/",
                    "http://billmoyers.com/series/creativity/"):
            with self.subTest(url=url), self.assertRaises(SourceError):
                source_url(url, context=True)

    def test_producer_response_redirect_requires_an_approved_production_record(self):
        value = deepcopy(next(s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                              if s["url"] == "https://billmoyers.com/series/creativity/"))
        for redirected in ("https://billmoyers.com/awards/1982", "https://example.org/series/creativity/"):
            value["resolvedUrl"] = redirected
            with self.subTest(redirected=redirected), self.assertRaises(SourceError):
                evidence(value, value["url"], context=True)

    def test_quiz_owner_history_is_context_only_and_requires_exact_record_paths(self):
        for path in ("/about.asp", "/index-cb.asp"):
            url = "https://collegebowl.com" + path
            source_url(url, context=True)
            with self.assertRaises(SourceError):
                source_url(url)
        for url in ("https://collegebowl.com/awards.asp", "https://collegebowl.com/about.asp?awards=1963",
                    "https://collegebowl.com/about.asp#awards", "https://collegebowl.com/%61bout.asp",
                    "https://collegebowl.com/about.asp;awards=1963",
                    "https://billmoyers.com/series/creativity/;awards=1982",
                    "https://collegebowl.com/series/creativity/", "https://billmoyers.com/about.asp",
                    "https://collegebowl.com.example.org/about.asp", "https://user@collegebowl.com/about.asp",
                    "https://collegebowl.com:443/about.asp", "http://collegebowl.com/about.asp"):
            with self.subTest(url=url), self.assertRaises(SourceError):
                source_url(url, context=True)

    def test_quiz_owner_redirect_cannot_expand_to_unreviewed_records(self):
        value = deepcopy(next(s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                              if s["url"] == "https://collegebowl.com/about.asp"))
        evidence(value, value["url"], context=True)
        for redirected in ("https://collegebowl.com/awards.asp", "https://www.collegebowl.com/about.asp",
                           "https://collegebowl.com/index-cb.asp?year=1963"):
            value["resolvedUrl"] = redirected
            with self.subTest(redirected=redirected), self.assertRaises(SourceError):
                evidence(value, value["url"], context=True)

    def test_context_rejects_other_hosts_and_disguised_authorities(self):
        for authority in ("televisionacademy.com.example.org", "interviews.televisionacademy.com.example.org",
                          "user@interviews.televisionacademy.com", "interviews.televisionacademy.com:443",
                          "example.org"):
            with self.subTest(authority=authority), self.assertRaises(SourceError):
                source_url("https://" + authority + "/interviews/rita-moreno", context=True)
        with self.assertRaises(SourceError):
            source_url("http://interviews.televisionacademy.com/interviews/rita-moreno", context=True)

    def test_response_provenance_checks_requested_and_redirected_authorities(self):
        url = "https://www.televisionacademy.com/bios/rita-moreno"
        value = dict(url=url, resolvedUrl=url, status=200, sha256="0" * 64, byteCount=1, checkedAt="2026-10-03")
        evidence(value, url)
        value["resolvedUrl"] = "https://interviews.televisionacademy.com/interviews/rita-moreno"
        evidence(value, url, context=True)
        with self.assertRaises(SourceError):
            evidence(value, url)
        value["resolvedUrl"] = "https://example.org/interview"
        with self.assertRaises(SourceError):
            evidence(value, url, context=True)
        value["url"] = "https://example.org/interview"
        value["resolvedUrl"] = url
        with self.assertRaises(SourceError):
            evidence(value, value["url"], context=True)


class EmmyLineageReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        cls.decisions = {d["sourceSlug"]: d for p in ledger["programmes"] for d in p["decisions"]}

    def test_early_actor_heading_does_not_convert_variety_stars_into_scripted_leads(self):
        decision = self.decisions["best-actor"]
        for year in (1951, 1952, 1954):
            self.assertEqual(review_for_year(decision, year)["disposition"], "excluded")
            self.assertIsNone(category_for_year(decision, year))
        self.assertEqual(review_for_year(decision, 1953)["disposition"], "pending-review")
        self.assertEqual(category_for_year(decision, 1956), "lead-actor-in-a-comedy-series")
        # Excluding the performance keeps its requested source page and facts.
        lineage = load(SOURCE_DIR / "lineage-decisions.json")
        urls = {p["url"] for p in candidate_pages(load(SOURCE_DIR / "annual-indices.json")["years"], lineage)}
        for year in (1951, 1952, 1954):
            self.assertIn(f"https://www.televisionacademy.com/awards/nominees-winners/{year}/best-actor", urls)

    def test_early_actress_review_preserves_unavailable_source_programme_credits(self):
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        for year, slug in ((1951, "best-actress"), (1953, "best-comedienne")):
            decision = self.decisions[slug]
            self.assertEqual(category_for_year(decision, year), "lead-actress-in-a-comedy-series")
            page = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith(f"/{year}/{slug}"))
            self.assertEqual(page["winners"][0]["programmes"][0]["name"], "N/A")
            self.assertNotIn("mediaType", page["winners"][0])
            self.assertTrue(review_for_year(decision, year)["externalEvidence"])
        decision = self.decisions["best-comedienne"]
        self.assertEqual(review_for_year(decision, 1958)["disposition"], "excluded")
        self.assertEqual(review_for_year(decision, 1957)["disposition"], "pending-review")
        self.assertIsNone(category_for_year(decision, 1958))

    def test_adaptation_uses_original_writer_field_without_inventing_credit_roles(self):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        contexts = {s["url"]: s["context"] for s in ledger["contextSources"]}
        slug = "best-television-adaptation"
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1956/' + slug))
        self.assertEqual(contexts["https://www.televisionacademy.com/awards/nominees-winners/1956"],
                         "Writers Original Teleplay Writing Television Adaptation")
        self.assertEqual(category_for_year(self.decisions[slug], 1956), "writing-for-a-drama-series")
        self.assertEqual(page["sourceCategory"], "Best Television Adaptation")
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Paul Gregory", ""), ("Franklin Schaffner", "")])

    def test_adaptation_and_directing_remain_separate_awarded_contracts(self):
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        pages = {p["sourceUrl"].rsplit('/', 1)[-1]: p for p in snapshot["pages"] if p["year"] == 1956}
        adaptation = pages["best-television-adaptation"]["winners"][0]
        directing = pages["best-director-live-series"]["winners"][0]
        self.assertEqual(adaptation["programmes"], directing["programmes"])
        self.assertNotEqual(adaptation["sourceKey"], directing["sourceKey"])
        self.assertEqual([c["name"] for c in directing["credits"]], ["Franklin Schaffner"])
        self.assertEqual(category_for_year(self.decisions["best-director-live-series"], 1956),
                         "directing-for-a-drama-series")
        self.assertNotEqual(category_for_year(self.decisions["best-television-adaptation"], 1956),
                            category_for_year(self.decisions["best-director-live-series"], 1956))

    def test_skelton_uses_original_comedy_eligibility_and_keeps_missing_work_reference(self):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        contexts = {s["url"]: s["context"] for s in ledger["contextSources"]}
        slug = "best-comedian-or-comedienne"
        review = review_for_year(self.decisions[slug], 1952)
        url = "https://www.televisionacademy.com/awards/nominees-winners/1952/outstanding-comedy-series"
        self.assertIn("Best Comedy Show", contexts[url])
        self.assertIn("Winner Red Skelton Show NBC n/a", contexts[url])
        self.assertIn(url, review["externalEvidence"])
        self.assertEqual(category_for_year(self.decisions[slug], 1952), "lead-actor-in-a-comedy-series")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1952/' + slug))
        self.assertEqual(page["winners"][0]["programmes"][0]["name"], "N/A")
        self.assertEqual(page["winners"][0]["heading"], "Red Skelton")
        self.assertEqual(page["winners"][0]["credits"][0]["role"], "")

    def test_comedian_context_does_not_certify_separate_performance_fields(self):
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("September 30, 1951 on NBC", contexts["https://www.televisionacademy.com/bios/red-skelton"])
        self.assertIn("renamed The Red Skelton Hour in 1962", contexts["https://www.televisionacademy.com/bios/red-skelton"])
        self.assertIn("Skelton’s comic characters", contexts[
            "https://www.televisionacademy.com/news/hall-fame/red-skelton-hall-fame-tribute"])
        for slug, year in (("best-comedian", 1953), ("best-comedienne", 1956), ("best-comedienne", 1957)):
            self.assertIsNone(category_for_year(self.decisions[slug], year))
        self.assertIsNone(category_for_year(self.decisions["best-actor"], 1952))

    def test_original_college_quiz_winner_keeps_academy_facts_and_placeholder_credit(self):
        slug = "outstanding-program-achievement-in-the-field-of-panel-quiz-or-audience-participation"
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1963/' + slug))
        self.assertEqual(category_for_year(self.decisions[slug], 1963), "game-show")
        self.assertEqual(page["sourceCategory"],
                         "Outstanding Program Achievement In The Field Of Panel, Quiz Or Audience Participation")
        self.assertEqual(page["winnerCount"], 1)
        self.assertEqual(page["winners"][0]["programmes"][0]["name"], "G-E College Bowl")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["CBS"])
        self.assertEqual(page["winners"][0]["credits"], [{"name": "n/a", "role": ""}])

    def test_quiz_format_owner_context_distinguishes_radio_and_original_network_run(self):
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        about = contexts["https://collegebowl.com/about.asp"]
        history = contexts["https://collegebowl.com/index-cb.asp"]
        self.assertIn("two teams of competing students", about)
        self.assertIn("January 5, 1959", about)
        self.assertIn("Tossup question – Bonus question format", history)
        self.assertIn("CBS from 1959-63 and NBC from 1964-70", history)
        self.assertIn("produced or licensed by the College Bowl Company", history)
        self.assertNotIn("won an Emmy", history)
        review = review_for_year(self.decisions[
            "outstanding-program-achievement-in-the-field-of-panel-quiz-or-audience-participation"], 1963)
        self.assertEqual(review["years"], [1963])
        self.assertIn("not award recipients", review["reason"])

    def test_excluded_period_still_requires_exact_winner_keys_and_fingerprints(self):
        slug = "best-actor"
        review = deepcopy(review_for_year(self.decisions[slug], 1951))
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1951/' + slug))
        contexts = {s["url"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        arguments = ({1951: page["sourceUrl"]}, {page["sourceUrl"]: (1951, slug)},
                     {page["sourceUrl"]: page}, {"lead-actor-in-a-comedy-series"}, contexts)
        validate_review(review, *arguments)
        review["reviewedSourcePages"][0]["winnerSourceKeys"] = []
        with self.assertRaises(SourceError):
            validate_review(review, *arguments)

    def test_audit_counts_retained_excluded_periods_inside_pending_branches(self):
        from build_emmy_lineage_audit import build
        report = build()
        # Five personality years and an expressly headed cultural performance
        # remain under pending slugs, alongside nine retired-programme pages.
        self.assertEqual(report["summary"]["retainedScopeExcludedPageCount"], 16)
        self.assertEqual(report["summary"]["retainedScopeExcludedWinnerRecordCount"], 17)
        self.assertEqual(report["summary"]["publishedEmmyCatalogueCount"], 0)

    def test_miniseries_slug_does_not_reclassify_the_1973_single_programme(self):
        decision = self.decisions["outstanding-miniseries"]
        self.assertEqual(category_for_year(decision, 1973), "television-movie")
        self.assertEqual(category_for_year(decision, 1974), "limited-or-anthology-series")

    def test_merged_programme_period_uses_the_awarded_production_format(self):
        decision = self.decisions["outstanding-miniseries-or-movie"]
        self.assertEqual(category_for_year(decision, 1990), "television-movie")
        self.assertEqual(category_for_year(decision, 1991), "limited-or-anthology-series")
        self.assertEqual(category_for_year(decision, 1992), "limited-or-anthology-series")
        self.assertEqual(category_for_year(decision, 2011), "limited-or-anthology-series")
        for year in (2012, 2013):
            self.assertEqual(category_for_year(decision, year), "television-movie")
        self.assertEqual(decision["disposition"], "current-lineage")

    def test_reality_split_does_not_allocate_the_whole_older_field_to_one_successor(self):
        decision = self.decisions["outstanding-reality-program"]
        for year in (2004, 2005, 2006, 2012, 2013):
            self.assertEqual(category_for_year(decision, year), "structured-reality-program")
        for year in (2001, 2002, 2007, 2008, 2009, 2010, 2011):
            self.assertEqual(category_for_year(decision, year), "unstructured-reality-program")

    def test_original_miniseries_producer_does_not_replace_award_credits(self):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        contexts = {s["url"]: s["context"] for s in ledger["contextSources"]}
        url = "https://www.georgestevensjr.com/justice"
        self.assertIn("Separate But Equal 1991 two-part television miniseries", contexts[url])
        self.assertIn("The Murder of Mary Phagan 1988", contexts[url])
        self.assertIn("Thurgood 2011 movie", contexts[url])
        slug = "outstanding-miniseries-or-movie"
        self.assertIn(url, review_for_year(self.decisions[slug], 1991)["externalEvidence"])
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1991/' + slug))
        self.assertEqual(page["sourceCategory"], "Outstanding Drama/Comedy Special And Miniseries")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["ABC"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Stan Margulies", ""), ("George Stevens", "")])

    def test_explicit_cultural_performance_is_excluded_without_erasing_its_winner(self):
        slug = "outstanding-cultural-program"
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1997/' + slug))
        review = review_for_year(self.decisions[slug], 1997)
        self.assertEqual(review["disposition"], "excluded")
        self.assertEqual(page["sourceCategory"], "Outstanding Achievement In Cultural Programming - Performance")
        self.assertEqual(page["winners"][0]["credits"], [{"name": "Pilobolus Dance Theatre", "role": "",
                         "url": "https://www.televisionacademy.com/bios/pilobolus-dance-theatre"}])
        self.assertEqual(review["reviewedSourcePages"][0]["winnerSourceKeys"], [page["winners"][0]["sourceKey"]])
        self.assertIsNone(category_for_winner(self.decisions[slug], 1997, page["winners"][0]["sourceKey"]))
        self.assertEqual(review_for_year(self.decisions[slug], 1994)["disposition"], "pending-review")

    def test_reviewed_no_award_pins_the_empty_field_without_allocating_nominees(self):
        page = load(SOURCE_DIR / "official-winners-1949-2026.json")["noAwardPages"][0]
        review = deepcopy(review_for_year(self.decisions[
            "outstanding-single-performance-by-an-actor-in-a-supporting-role"], 1969))
        self.assertEqual(review["disposition"], "current-lineage")
        self.assertNotIn("currentCategory", review)
        self.assertEqual(review["winnerAllocations"], [])
        self.assertEqual(review["reviewedSourcePages"][0]["winnerSourceKeys"], [])
        self.assertEqual(page["nominationCount"], 3)
        url = page["sourceUrl"]
        contexts = {s["url"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        arguments = ({1969: url}, {url: (1969, url.rsplit('/', 1)[1])}, {url: page},
                     {"supporting-actor-in-a-limited-or-anthology-series-or-movie"}, contexts)
        validate_review(review, *arguments)
        review["winnerAllocations"] = [{"sourceKey": "unawarded-nominee"}]
        with self.assertRaises(SourceError):
            validate_review(review, *arguments)
        review["winnerAllocations"] = []
        review["reviewedSourcePages"][0]["sha256"] = "0" * 64
        with self.assertRaises(SourceError):
            validate_review(review, *arguments)

    def test_tied_single_supporting_performances_follow_both_ongoing_genres(self):
        slug = "outstanding-single-performance-by-a-supporting-actress-in-a-comedy-or-drama-series"
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1975/' + slug))
        self.assertEqual(page["winnerCount"], 2)
        targets = {w["heading"]: category_for_winner(self.decisions[slug], 1975, w["sourceKey"])
                   for w in page["winners"]}
        self.assertEqual(targets, {"Zohra Lampert": "guest-actress-in-a-drama-series",
                                  "Cloris Leachman": "guest-actress-in-a-comedy-series"})
        review = review_for_year(self.decisions[slug], 1975)
        self.assertIsNone(category_for_year(self.decisions[slug], 1975))
        self.assertEqual(review["reviewedSourcePages"][0]["winnerSourceKeys"],
                         [w["sourceKey"] for w in page["winners"]])
        self.assertIn("Supporting Actress", page["sourceCategory"])
        self.assertTrue(all(c["role"] == "" for w in page["winners"] for c in w["credits"]))

    def test_western_single_performance_keeps_part_ii_and_original_year_eligibility(self):
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        url = "https://www.televisionacademy.com/awards/nominees-winners/1978/outstanding-lead-actress-in-a-drama-series"
        self.assertIn("Nominee Fionnula Flanagan How The West Was Won", contexts[url])
        self.assertIn("How the West was Won, Part II", contexts[
            "https://www.televisionacademy.com/shows/how-west-was-won"])
        slug = "outstanding-single-performance-by-a-supporting-actor-in-a-comedy-or-drama-series"
        review = review_for_year(self.decisions[slug], 1978)
        self.assertIn(url, review["externalEvidence"])
        self.assertIn("1977 Limited Series", review["reason"])
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1978/' + slug))
        self.assertEqual(page["winners"][0]["heading"], "Ricardo Montalban")
        self.assertEqual(page["winners"][0]["credits"][0]["role"], "")

    def test_single_supporting_actress_keeps_the_original_anthology_production(self):
        slug = "outstanding-single-performance-by-an-actress-in-a-supporting-role"
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1969/' + slug))
        self.assertEqual(category_for_year(self.decisions[slug], 1969),
                         "supporting-actress-in-a-limited-or-anthology-series-or-movie")
        self.assertEqual(page["winners"][0]["heading"], "Anna Calder-Marshall")
        self.assertEqual(page["winners"][0]["programmes"][0]["name"], "Male of the Species Prudential's On Stage")
        self.assertEqual(page["winners"][0]["credits"][0]["role"], "")
        self.assertIn("anthology episode versus parent", self.decisions[
            "outstanding-lead-actor-in-a-miniseries-or-a-movie"]["reason"].casefold())

    def test_concert_recording_does_not_inherit_the_original_event_livestream(self):
        slug = "outstanding-special-class-not-exclusively-made-for-television-variety-music-comedy-event-programs"
        self.assertEqual(category_for_year(self.decisions[slug], 2008), "variety-special-pre-recorded")
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("broadcasted online and later released on DVD", contexts[
            "https://ericclapton.com/pages/timeline-2000s"])
        programme = contexts["https://www.pbs.org/wnet/gperf/eric-clapton-crossroads-guitar-festival-chicago-chicago-blues-overview/404/"]
        self.assertIn("November 28, 2007", programme)
        schedule = next(v for k, v in contexts.items() if k.endswith('/pbs-offers-music-and-dance-lovers-exciting-new-performance-specials-throughout-march-and-april-february-13-2008/'))
        self.assertIn('Chicago" (R) Wednesday, March 19, 2008, 9:00-11:00 p.m. ET', schedule)
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/2008/' + slug))
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["PBS"])
        self.assertEqual(len(page["winners"][0]["credits"]), 6)
        self.assertEqual(page["winners"][0]["credits"][-1]["role"], "Series Producer")

    def test_smithsonian_review_keeps_both_tied_winners_and_later_empty_credits(self):
        slug = "outstanding-informational-series"
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        tied = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith('/1987/' + slug))
        self.assertEqual([w["heading"] for w in tied["winners"]],
                         ["Smithsonian World", "Unknown Chaplin American Masters"])
        self.assertTrue(all(len(w["credits"]) == 2 for w in tied["winners"]))
        self.assertEqual(review_for_year(self.decisions[slug], 1987)["reviewedSourcePages"][0]["winnerSourceKeys"],
                         [w["sourceKey"] for w in tied["winners"]])
        for year in (1987, 1990):
            self.assertEqual(category_for_year(self.decisions[slug], year), "documentary-or-nonfiction-series")
        later = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith('/1990/' + slug))
        self.assertEqual(later["winners"][0]["credits"], [])
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        finding_aid = contexts["https://sirismm.si.edu/EADpdfs/SIA.FA91-164.pdf"]
        self.assertIn("6 seasons, each with 5-7", finding_aid)
        self.assertIn("Documentary television programs", finding_aid)
        self.assertIn('Treasures," one and two hour versions', finding_aid)
        self.assertIn("The Unknown Chaplin (Jul 1986)", contexts[
            "https://www.pbs.org/wnet/americanmasters/masters/charlie-chaplin/"])

    def test_school_documentary_filming_year_does_not_shift_its_emmy_ceremony(self):
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("(1993, 90 min.)", contexts["https://videoverite.tv/pages/storemain-2011.html"])
        self.assertIn("Filmed over the course of one year", contexts[
            "https://videoverite.tv/pages/iamapromisemain-2011.html"])
        slug = "outstanding-informational-special"
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1994/' + slug))
        self.assertEqual(page["winners"][0]["heading"], "I Am A Promise: The Children Of Stanton Street Ele")
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Alan Raymond", ""), ("SUSAN RAYMOND", "")])

    def test_new_production_records_are_exact_context_only_for_request_and_redirect(self):
        from validate_emmy_source import PRODUCER_CONTEXT_PATHS
        hosts = {"www.georgestevensjr.com", "ericclapton.com", "sirismm.si.edu", "videoverite.tv", "www.pbs.org",
                 "amblin.com", "peabodyawards.com", "findingaids.library.nyu.edu", "www.tonyawards.com",
                 "www.history.navy.mil", "www.lucasfilm.com", "billzarchy.com", "dcmp.org",
                 "www.latimes.com", "www.worldradiohistory.com", "americanarchive.org",
                 "www.duckprods.com", "catalog.afi.com", "www.afi.com", "www.congress.gov",
                 "www.paleycenter.org", "www.charlottegrossman.com", "www.rai.it",
                 "www.joegantz.com", "www.ushmm.org", "www.deborahdickson.com", "www.acmi.net.au", "newsroom.ucla.edu"}
        contexts = load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
        for host in hosts:
            for path in PRODUCER_CONTEXT_PATHS[host]:
                url = "https://" + host + path
                value = deepcopy(next(s for s in contexts if s["url"] == url))
                evidence(value, url, context=True)
                with self.subTest(url=url), self.assertRaises(SourceError):
                    evidence(value, url)
                for rejected in (url + "?award=1991", url + "#award", url + ";award=1991",
                                 "http://" + host + path, "https://user@" + host + path,
                                 "https://" + host + ":443" + path, "https://" + host + "/unreviewed/"):
                    with self.subTest(rejected=rejected), self.assertRaises(SourceError):
                        source_url(rejected, context=True)
                    value["resolvedUrl"] = rejected
                    with self.subTest(redirected=rejected), self.assertRaises(SourceError):
                        evidence(value, url, context=True)

    def test_paley_record_query_cannot_select_a_different_or_unreviewed_production(self):
        url = "https://www.paleycenter.org/collection/item?item=T80%3A0637"
        value = next(s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"] if s["url"] == url)
        for query in ("", "?item=T80%3A0638", "?item=T80:0637", "?item=T80%3a0637",
                      "?item=T80%3A0637&award=1980", "?award=1980&item=T80%3A0637",
                      "?item=T80%3A0637&item=T80%3A0638"):
            rejected = "https://www.paleycenter.org/collection/item" + query
            with self.subTest(request=rejected), self.assertRaises(SourceError):
                evidence({**value, "url": rejected}, rejected, context=True)
            with self.subTest(redirect=rejected), self.assertRaises(SourceError):
                evidence({**value, "resolvedUrl": rejected}, url, context=True)

    def test_body_human_series_keeps_anthology_award_instead_of_substituting_one_film(self):
        slug = "outstanding-informational-series"
        self.assertEqual(category_for_year(self.decisions[slug], 1978), "documentary-or-nonfiction-series")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1978/' + slug))
        winner = page["winners"][0]
        self.assertEqual(page["sourceCategory"], "Outstanding Informational Series")
        self.assertEqual(winner["heading"], "The Body Human")
        self.assertEqual(winner["sourceDetailLines"], ["CBS"])
        self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]],
                         [("Alfred R. Kelman", ""), ("Thomas W. Moore", "")])
        contexts = {s["url"]: s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        paley = contexts["https://www.paleycenter.org/collection/item?item=T80%3A0637"]
        self.assertIn("CBS - TV series, 1977-", paley["context"])
        rai = contexts["https://www.rai.it/dl/doc/2025/04/24/1745502034846_prix_italia_1948_2024.pdf"]
        self.assertEqual(rai["pageNumbers"], [51])
        self.assertIn("The Body Human: The Miracle Months", rai["context"])
        self.assertIn("first stages of human life in the womb", rai["context"])

    def test_magic_sense_keeps_emmy_year_and_sole_producer_not_museum_crew(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1980), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1980/' + slug))
        self.assertEqual(page["sourceCategory"], "Outstanding Informational Program")
        winner = page["winners"][0]
        self.assertEqual(winner["heading"], "The Body Human: The Magic Sense")
        self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]], [("Robert E. Fuisz", "Producer")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://www.paleycenter.org/collection/item?item=T80%3A0637")
        self.assertIn("September 6, 1979", context)
        self.assertIn("Alexander Scourby … Narrator", context)
        self.assertEqual(winner["sourceDetailLines"], ["CBS"])

    def test_medical_specials_keep_all_recipients_without_host_or_filmmaker_substitution(self):
        slug = "outstanding-informational-special"
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        source = "https://www.charlottegrossman.com/health-and-medicine"
        self.assertIn("Bionic Breakthrough. The Body Human: The Living Code", contexts[source])
        self.assertIn("doctors, their patients and modern technology in medicine", contexts[source])
        for year, title, names in (
            (1981, "The Body Human: The Bionic Breakthrough",
             ["Charles A. Bangert", "Robert E. Fuisz", "Alfred R. Kelman", "Thomas W. Moore", "Nancy Smith"]),
            (1983, "The Body Human: The Living Code",
             ["Charles A. Bangert", "Robert E. Fuisz", "Franklin Getchell", "Alfred R. Kelman", "Thomas W. Moore", "Nancy Smith"]),
        ):
            with self.subTest(year=year):
                self.assertEqual(category_for_year(self.decisions[slug], year), "documentary-or-nonfiction-special")
                review = review_for_year(self.decisions[slug], year)
                self.assertIn(source, review["externalEvidence"])
                page = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith('/' + str(year) + '/' + slug))
                winner = page["winners"][0]
                self.assertEqual(page["sourceCategory"], "Outstanding Informational Special")
                self.assertEqual(winner["heading"], title)
                self.assertEqual(winner["sourceDetailLines"], ["CBS"])
                self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]], [(n, "") for n in names])

    def test_single_appearance_label_does_not_turn_miniseries_into_ongoing_drama(self):
        actor = self.decisions["outstanding-lead-actor-for-a-single-appearance-in-a-drama-or-comedy-series"]
        actress = self.decisions["outstanding-lead-actress-for-a-single-appearance-in-a-drama-or-comedy-series"]
        for year in (1976, 1977):
            self.assertEqual(category_for_year(actor, year), "lead-actor-in-a-limited-or-anthology-series-or-movie")
        self.assertEqual(category_for_year(actress, 1976), "lead-actress-in-a-limited-or-anthology-series-or-movie")
        # Original ongoing-drama eligibility and separate single-appearance
        # evidence distinguish these from the limited-series predecessors.
        self.assertEqual(category_for_year(actor, 1978), "guest-actor-in-a-drama-series")
        for year in (1977, 1978):
            self.assertEqual(category_for_year(actress, year), "guest-actress-in-a-drama-series")

    def test_taxicab_museum_tie_keeps_both_original_titles_and_all_seven_unavailable_roles(self):
        slug = "outstanding-informational-special"
        decision = self.decisions[slug]
        review = review_for_year(decision, 1995)
        self.assertEqual(category_for_year(decision, 1995), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1995/' + slug))
        self.assertEqual([w["heading"] for w in page["winners"]],
                         ["Taxicab Confessions", "The United States Holocaust Memorial Museum Presen"])
        self.assertEqual(review["reviewedSourcePages"][0]["winnerSourceKeys"],
                         [w["sourceKey"] for w in page["winners"]])
        self.assertEqual([w["sourceDetailLines"] for w in page["winners"]], [["HBO"], ["HBO"]])
        self.assertEqual([[c["name"] for c in w["credits"]] for w in page["winners"]], [
            ["Joe Gantz", "Harry Gantz", "Sheila Nevins"],
            ["Kary Antholis", "Michael Berenbaum", "Raye Farr", "Sheila Nevins"]])
        self.assertTrue(all(c["role"] == "" for w in page["winners"] for c in w["credits"]))
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("six miniature hidden cameras", contexts["https://www.joegantz.com/filmography.html"])
        self.assertIn("questions through the driver", contexts["https://www.joegantz.com/filmography.html"])
        self.assertIn("produced in 1995 by HBO", contexts[
            "https://www.ushmm.org/remember/holocaust-reflections-testimonies/one-survivor-remembers"])
        self.assertIn("One Survivor Remembers", contexts["https://www.televisionacademy.com/bios/lawrence-silk"])
        self.assertIn("Museum Presen HBO", contexts["https://www.televisionacademy.com/bios/lawrence-silk"])

    def test_abortion_documentary_preserves_sole_academy_recipient_not_full_filmmaking_team(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1992), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1992/' + slug))
        self.assertEqual(page["winners"][0]["heading"], "Abortion: Desperate Choices")
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]], [("Susan Froemke", "")])
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["HBO"])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://www.deborahdickson.com/filmography")
        self.assertIn("ABORTION: DESPERATE CHOICES (1992)", context)
        self.assertIn("documentary film focuses on unplanned pregnancies", context)

    def test_mgm_hosted_history_preserves_original_series_award_and_sole_recipient(self):
        slug = "outstanding-informational-series"
        self.assertEqual(category_for_year(self.decisions[slug], 1992), "hosted-nonfiction-series-or-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1992/' + slug))
        self.assertEqual(page["sourceCategory"], "Outstanding Informational Series")
        self.assertEqual(page["winners"][0]["heading"], "MGM: When the Lion Roars")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["TNT"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]], [("JONI LEVIN", "")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://www.acmi.net.au/works/83212--mgm-when-the-lion-roars/")
        self.assertIn("three segments", context)
        self.assertIn("Hosted by the ever suave Patrick Stewart", context)

    def test_kennedy_narrated_film_preserves_ceremony_not_production_or_listing_date(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1984), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1984/' + slug))
        self.assertEqual(page["winners"][0]["heading"], "America Remembers John F. Kennedy")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["SYN"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]], [("Thomas F. Horton", "")])
        contexts = {s["url"]: s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("1983 documentary produced by Thomas Horton Associates", contexts[
            "https://newsroom.ucla.edu/stories/jfk-ucla-film-and-television-archive-249480"]["context"])
        record = contexts["https://www.worldradiohistory.com/Archive-TV-Radio-Age/80s/1985/Television-Radio-Age-1985-01-07.pdf"]
        self.assertEqual(record["pageNumbers"], [261])
        self.assertIn("ON THE AIR", record["context"])
        self.assertIn("Ken-\nnedy- 2- hour documentary narrated \nby Hal Holbrook.", record["context"])
        self.assertEqual(review_for_year(self.decisions[slug], 1985)["disposition"], "pending-review")

    def test_agnes_profile_preserves_documentary_award_without_converting_subject_into_performer(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1987), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1987/' + slug))
        self.assertEqual(page["sourceCategory"], "Outstanding Informational Special")
        self.assertEqual(page["winners"][0]["heading"], "Dance in America: Agnes, The Indomitable DeMille")
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Judy Kinberg", ""), ("Jac Venza", "")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://www.paleycenter.org/collection/item?item=T88%3A0429")
        self.assertIn("GENRE: Dance; Arts documentaries", context)
        self.assertIn("de Mille, Agnes … Special Guest", context)

    def test_guest_review_preserves_original_headings_and_pins_actual_context(self):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        contexts = {s["url"]: s["context"] for s in ledger["contextSources"]}
        slug = "outstanding-lead-actress-for-a-single-appearance-in-a-drama-or-comedy-series"
        page = next(p for p in snapshot["pages"] if p["year"] == 1978 and p["sourceUrl"].endswith('/' + slug))
        self.assertIn("Lead Actress", page["sourceCategory"])
        self.assertEqual(page["winners"][0]["heading"], "Rita Moreno")
        url = "https://interviews.televisionacademy.com/interviews/rita-moreno"
        self.assertIn("Emmy-winning guest appearances", contexts[url])
        self.assertIn(url, review_for_year(self.decisions[slug], 1978)["externalEvidence"])
        self.assertIn("Nominee Michael Learned The Waltons", contexts[
            "https://www.televisionacademy.com/awards/nominees-winners/1977/outstanding-lead-actress-in-a-drama-series"])

    def test_reality_honors_supply_context_without_creating_an_emmy_winner(self):
        decision = self.decisions["outstanding-reality-program"]
        review = review_for_year(decision, 2010)
        self.assertEqual([p["year"] for p in review["reviewedSourcePages"]], [2010])
        self.assertIn("Academy Honors", review["reason"])
        self.assertIn("https://www.televisionacademy.com/features/news/latest-news/dana-delany-host-fourth-television-academy-honors",
                      review["externalEvidence"])

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
        self.assertEqual(category_for_year(self.decisions[support_slug], 1978), "guest-actor-in-a-drama-series")

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
        # Another season's limited eligibility must not override the 1978
        # production's ordinary Drama eligibility and single-performance award.
        self.assertEqual(category_for_year(decision, 1978), "guest-actor-in-a-drama-series")

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
                                  ("best-western-or-adventure-series", (1955,), "Stories of the Century"),
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
        self.assertEqual(category_for_year(self.decisions["outstanding-informational-series"], 1994),
                         "hosted-nonfiction-series-or-special")
        self.assertEqual(category_for_year(self.decisions["outstanding-informational-special"], 1994),
                         "documentary-or-nonfiction-special")

    def test_documentary_context_does_not_accept_only_one_side_of_an_informational_tie(self):
        decision = self.decisions["outstanding-informational-series"]
        for year in (1988, 1989, 1991):
            self.assertEqual(category_for_year(decision, year), "documentary-or-nonfiction-series")
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        tied = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith("/1988/outstanding-informational-series"))
        self.assertEqual(tied["sourceCategory"], "Outstanding Informational Series")
        self.assertEqual(len(tied["winners"]), 2)
        reviewed = review_for_year(decision, 1988)["reviewedSourcePages"]
        self.assertEqual(reviewed[0]["winnerSourceKeys"], [w["sourceKey"] for w in tied["winners"]])
        for winner in tied["winners"]:
            self.assertEqual(category_for_winner(decision, 1988, winner["sourceKey"]),
                             "documentary-or-nonfiction-series")
        # Other reviewed ties cannot certify the Olivier/Planet Earth pair.
        for year in (1986,):
            self.assertEqual(review_for_year(decision, year)["disposition"], "pending-review")
            self.assertIsNone(category_for_year(decision, year))
            page = next(p for p in snapshot["pages"]
                        if p["sourceUrl"].endswith(f"/{year}/outstanding-informational-series"))
            self.assertEqual(len(page["winners"]), 2)
            for winner in page["winners"]:
                self.assertIsNone(category_for_winner(decision, year, winner["sourceKey"]))

    def test_public_service_documentary_win_is_not_a_narrator_recognition(self):
        decision = self.decisions["outstanding-program-achievement-in-the-field-of-public-service"]
        snapshot = load(SOURCE_DIR / "official-winners-1949-2026.json")
        for year in (1960, 1961):
            self.assertEqual(category_for_year(decision, year), "documentary-or-nonfiction-series")
            page = next(p for p in snapshot["pages"] if p["sourceUrl"].endswith(f"/{year}/" + decision["sourceSlug"]))
            self.assertIn("Public Service", page["sourceCategory"])
            # The tribute proves the programme format, not an Emmy recipient:
            # its narrator must not be inserted into the original blank credits.
            self.assertNotIn("Walter Cronkite", [c["name"] for c in page["winners"][0]["credits"]])

    def test_variety_special_slug_does_not_turn_the_1968_series_into_a_live_special(self):
        decision = self.decisions["outstanding-variety-music-or-comedy-special"]
        self.assertEqual(category_for_year(decision, 1968), "variety-series")
        self.assertIsNone(category_for_year(decision, 2017))
        self.assertEqual(category_for_year(decision, 2018), "variety-special-live")

    def test_special_class_live_route_uses_broadcast_evidence_not_the_title(self):
        decision = self.decisions["outstanding-special-class-programs"]
        self.assertEqual(category_for_year(decision, 2016), "variety-special-live")
        # Sweeney Todd (Live From Lincoln Center) cannot inherit that route
        # merely because Live occurs in its title.
        self.assertEqual(category_for_year(decision, 2015), "variety-special-pre-recorded")
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        url = "https://www.televisionacademy.com/features/news/mix/smooth-moves"
        context = next(s["context"] for s in ledger["contextSources"] if s["url"] == url)
        self.assertIn("was broadcast live from Warner Bros. Studios", context)
        self.assertIn(url, review_for_year(decision, 2016)["externalEvidence"])

    def test_filmed_documentaries_keep_their_original_variety_award(self):
        decision = self.decisions["outstanding-variety-music-or-comedy-special"]
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        for year, title, recipients in ((2004, "Elaine Stritch: At Liberty", 8),
                                         (2008, "Mr. Warmth: The Don Rickles Project", 4)):
            with self.subTest(year=year):
                page = next(p for p in pages if p["sourceUrl"].endswith(f"/{year}/" + decision["sourceSlug"]))
                winner = page["winners"][0]
                self.assertEqual(winner["heading"], title)
                self.assertEqual(len(winner["credits"]), recipients)
                self.assertEqual(category_for_winner(decision, year, winner["sourceKey"]),
                                 "variety-special-pre-recorded")
                self.assertIn("Variety", page["sourceCategory"])
                self.assertNotIn("documentary-or-nonfiction-special",
                                 [category_for_winner(decision, year, w["sourceKey"]) for w in page["winners"]])

    def test_live_singing_does_not_turn_an_edited_film_into_a_live_telecast(self):
        decision = self.decisions["outstanding-variety-music-or-comedy-special"]
        self.assertEqual(category_for_year(decision, 2007), "variety-special-pre-recorded")
        context = next(s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"].endswith("/story-groundbreaking-tony-bennett-special-premieres"))
        self.assertIn("shot their segments live", context["context"])
        self.assertIn("damaged film", context["context"])
        self.assertIn("In editing", context["context"])
        self.assertEqual(context["resolvedUrl"],
                         "https://www.televisionacademy.com/features/news/events/story-groundbreaking-tony-bennett-special-premieres")
        # The next annual winner is an Olympic telecast, whose actual broadcast
        # must be reviewed rather than inheriting its venue's live performance.
        self.assertIsNone(category_for_year(decision, 2006))

    def test_original_recorded_specials_preserve_years_and_credit_gaps(self):
        decision = self.decisions["outstanding-variety-music-or-comedy-special"]
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        for year in (1959, 1973):
            self.assertEqual(category_for_year(decision, year), "variety-special-pre-recorded")
        page = next(p for p in pages if p["sourceUrl"].endswith("/1959/" + decision["sourceSlug"]))
        self.assertEqual(page["winners"][0]["credits"][0]["name"], "n/a")
        self.assertNotIn("Edward Stephenson", [c["name"] for c in page["winners"][0]["credits"]])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"].endswith("/evening-liza-z"))
        self.assertIn("first aired in 1972 on NBC", context)
        self.assertIn("April 2006 premiere on Showtime", context)
        self.assertIn("shot as it was in 16mm", context)
        self.assertNotIn(2006, review_for_year(decision, 1973)["years"])

    def test_tony_profile_does_not_shift_the_award_to_its_publication_year(self):
        decision = self.decisions["outstanding-special-class-programs"]
        self.assertEqual(category_for_year(decision, 2012), "variety-special-live")
        self.assertNotIn(2013, review_for_year(decision, 2012)["years"])
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith("/2012/" + decision["sourceSlug"]))
        self.assertEqual(page["winners"][0]["heading"], "65th Annual Tony Awards")
        self.assertEqual(len(page["winners"][0]["credits"]), 3)
        self.assertEqual([c["role"] for c in page["winners"][0]["credits"]], ["", "", ""])
        self.assertIn("https://www.televisionacademy.com/features/emmy-magazine/me-and-my-emmy/me-and-my-emmy-glenn-weiss",
                      review_for_year(decision, 2012)["externalEvidence"])

    def test_educational_predecessors_require_the_actual_hosted_format(self):
        decision = self.decisions["achievements-in-educational-television"]
        for year in (1962, 1966):
            self.assertEqual(category_for_year(decision, year), "hosted-nonfiction-series-or-special")
        # The earlier local educational winner cannot inherit a later programme's
        # hosted format merely from the Educational Television category slug.
        self.assertIsNone(category_for_year(decision, 1951))
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("anchoring David Brinkley's Journal",
                      contexts["https://interviews.televisionacademy.com/interviews/david-brinkley"])
        self.assertIn("format of her cooking show",
                      contexts["https://interviews.televisionacademy.com/interviews/julia-child"])
        for year in (1962, 1966):
            self.assertIn("https://www.televisionacademy.com/features/news/awards-news/emmy-rules-changes-191217",
                          review_for_year(decision, year)["externalEvidence"])

    def test_host_format_context_does_not_rewrite_educational_award_credits(self):
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        slug = "achievements-in-educational-television"
        child = next(p for p in pages if p["sourceUrl"].endswith("/1966/" + slug))["winners"][0]
        self.assertEqual(child["heading"], "The French Chef")
        self.assertEqual(child["sourceDetailLines"], ["NET"])
        self.assertEqual([(c["name"], c["role"]) for c in child["credits"]], [("Julia Child", "")])
        brinkley = next(p for p in pages if p["sourceUrl"].endswith("/1962/" + slug))["winners"][0]
        self.assertEqual(brinkley["heading"], "David Brinkley's Journal")
        self.assertEqual(brinkley["sourceDetailLines"], ["NBC"])
        self.assertEqual([(c["name"], c["role"]) for c in brinkley["credits"]], [("n/a", "")])

    def test_informational_documentaries_are_not_scripted_movies_or_later_franchises(self):
        decision = self.decisions["outstanding-informational-special"]
        for year in (1979, 1993):
            self.assertEqual(category_for_year(decision, year), "documentary-or-nonfiction-special")
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("documentary Lucy and Desi- A Home Movie",
                      contexts["https://interviews.televisionacademy.com/interviews/lucie-arnaz"])
        self.assertIn("Scared Straight! a documentary",
                      contexts["https://interviews.televisionacademy.com/interviews/dixon-dern"])
        self.assertIsNone(category_for_year(self.decisions["outstanding-individual-achievement-informational-programming"], 1979))

    def test_documentary_format_review_preserves_the_original_programme_recipients(self):
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        scared = next(p for p in pages if p["sourceUrl"].endswith("/1979/outstanding-informational-special"))
        self.assertEqual(scared["sourceCategory"], "Outstanding Informational Program")
        self.assertEqual(scared["winners"][0]["sourceDetailLines"], ["SYN"])
        self.assertEqual([(c["name"], c["role"]) for c in scared["winners"][0]["credits"]], [("Arnold Shapiro", "")])
        lucy = next(p for p in pages if p["sourceUrl"].endswith("/1993/outstanding-informational-special"))["winners"][0]
        self.assertEqual(lucy["sourceDetailLines"], ["NBC"])
        self.assertEqual([(c["name"], c["role"]) for c in lucy["credits"]],
                         [("Lucie Arnaz", "Executive Producer"), ("Don Buford", "Producer"),
                          ("Laurence Luckinbill", "Executive Producer")])

    def test_walters_specials_title_retains_the_original_hosted_series_award(self):
        decision = self.decisions["outstanding-informational-series"]
        self.assertEqual(category_for_year(decision, 1983), "hosted-nonfiction-series-or-special")
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"].endswith("/shows/barbara-walters-specials"))
        self.assertIn("in-depth interviews conducted by journalist Barbara Walters", context)
        self.assertIn("Ten Most Fascinating People Specials in 1993", context)
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith("/1983/outstanding-informational-series"))
        self.assertEqual(page["sourceCategory"], "Outstanding Informational Series")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["ABC"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Beth Polson", ""), ("Barbara Walters", "")])

    def test_broadcaster_film_dates_do_not_replace_emmy_years_or_award_recipients(self):
        decision = self.decisions["outstanding-informational-special"]
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        for year, subject, production in ((1989, "Lillian Gish", "(Jul 1988)"),
                                           (1991, "Edward R. Murrow", "(Jul 1990)")):
            with self.subTest(year=year):
                self.assertEqual(category_for_year(decision, year), "documentary-or-nonfiction-special")
                review = review_for_year(decision, year)
                self.assertEqual(review["years"], [year])
                page = next(p for p in pages if p["sourceUrl"].endswith(f"/{year}/outstanding-informational-special"))
                self.assertEqual(page["sourceCategory"], "Outstanding Informational Special")
                credits = page["winners"][0]["credits"]
                self.assertEqual(len(credits), 4)
                self.assertNotIn(subject, [c["name"] for c in credits])
                self.assertEqual([c["role"] for c in credits], ["", "", "", ""])
                contexts = [s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                            if s["url"] in review["externalEvidence"]]
                self.assertTrue(any(production in c for c in contexts))

    def test_moyers_hosted_series_preserve_every_original_programme_credit(self):
        decision = self.decisions["outstanding-informational-series"]
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        for year, title, recipients in (
                (1982, "Creativity with Bill Moyers",
                 ["Charles Grinker", "Merton Y. Koplin", "Betsy McCarthy", "Bill Moyers"]),
                (1984, "A Walk Through the 20th Century With Bill Moyers",
                 ["Ronald Blumer", "Sanford H. Fisher", "Charles Grinker", "David Grubin",
                  "Merton Y. Koplin", "Betsy McCarthy", "Bill Moyers"]),
                (1993, "Healing And The Mind With Bill Moyers",
                 ["David Grubin", "Alice Markowitz", "Bill Moyers", "JUDITH DAVIDSON MOYERS"])):
            with self.subTest(year=year):
                self.assertEqual(category_for_year(decision, year), "hosted-nonfiction-series-or-special")
                review = review_for_year(decision, year)
                self.assertEqual(review["years"], [year])
                page = next(p for p in pages if p["sourceUrl"].endswith(f"/{year}/outstanding-informational-series"))
                self.assertEqual(page["sourceCategory"], "Outstanding Informational Series")
                winner = page["winners"][0]
                self.assertEqual(winner["heading"], title)
                self.assertEqual(winner["sourceDetailLines"], ["PBS"])
                self.assertEqual([c["name"] for c in winner["credits"]], recipients)
                self.assertEqual([c["role"] for c in winner["credits"]], [""] * len(recipients))
                self.assertEqual(review["reviewedSourcePages"][0]["winnerSourceKeys"], [winner["sourceKey"]])

    def test_documentary_description_does_not_erase_the_actual_hosted_interview_format(self):
        ledger = load(SOURCE_DIR / "lineage-decisions.json")
        contexts = {s["url"]: s["context"] for s in ledger["contextSources"]}
        healing = "https://billmoyers.com/series/healing-and-the-mind/"
        self.assertIn("is a documentary series", contexts[healing])
        self.assertIn("five-part series of provocative interviews", contexts[healing])
        review = review_for_year(self.decisions["outstanding-informational-series"], 1993)
        self.assertEqual(review["currentCategory"], "hosted-nonfiction-series-or-special")
        self.assertIn(healing, review["externalEvidence"])
        ownership = contexts["https://billmoyers.com/about-us/"]
        self.assertIn("journalism produced by Bill Moyers and his team", ownership)
        self.assertIn("rights to the company’s work were assigned to Doctoroff Media Group", ownership)

    def test_reviewed_hosted_productions_cannot_certify_partial_ties(self):
        decision = self.decisions["outstanding-informational-series"]
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        for year, count in ((1986, 2),):
            with self.subTest(year=year):
                self.assertEqual(review_for_year(decision, year)["disposition"], "pending-review")
                page = next(p for p in pages if p["sourceUrl"].endswith(f"/{year}/outstanding-informational-series"))
                self.assertEqual(len(page["winners"]), count)
                for winner in page["winners"]:
                    self.assertIsNone(category_for_winner(decision, year, winner["sourceKey"]))
        self.assertIsNone(category_for_year(self.decisions["outstanding-individual-achievement-informational-programming"], 1984))

    def test_hallmark_supporting_awards_keep_the_generic_anthology_credit(self):
        slug = "best-series-supporting-actress"
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        for year, recipient in ((1962, "Pamela Brown"), (1964, "Ruth White")):
            page = next(p for p in pages if p["sourceUrl"].endswith(f"/{year}/{slug}"))
            winner = page["winners"][0]
            self.assertEqual(category_for_year(self.decisions[slug], year),
                             "supporting-actress-in-a-limited-or-anthology-series-or-movie")
            self.assertEqual(page["sourceCategory"], "Outstanding Performance In A Supporting Role By An Actress")
            self.assertEqual(winner["heading"], recipient)
            self.assertEqual([p["name"] for p in winner["programmes"]], ["Hallmark Hall of Fame"])
            self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]], [(recipient, "")])
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("restaged it in 1964", contexts[
            "https://www.televisionacademy.com/features/news/features/ten-remember"])
        self.assertIn("Outstanding Single Performance By An Actress In A Leading Role", contexts[
            "https://www.televisionacademy.com/awards/nominees-winners/1962/outstanding-lead-actress-in-a-miniseries-or-a-movie"])

    def test_nile_drama_format_does_not_resolve_a_separate_individual_award(self):
        slug = "special-classification-of-outstanding-program-and-individual-achievement-docu-drama"
        self.assertEqual(category_for_year(self.decisions[slug], 1972), "limited-or-anthology-series")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1972/' + slug))
        self.assertIn("Docu-Drama", page["sourceCategory"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]], [("Christopher Ralling", "")])
        individual = self.decisions["special-classifications-of-individual-achievements"]
        self.assertIsNone(category_for_year(individual, 1972))
        url = "https://peabodyawards.com/award-profile/the-search-for-the-nile/"
        context = next(s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"] if s["url"] == url)
        self.assertIn("six-part chronicle", context["context"])
        self.assertIn("scripts", context["context"])
        with self.assertRaises(SourceError):
            evidence(context, url)  # Another award institution supplies format, never Emmy results.

    def test_meeting_of_minds_hosted_history_keeps_the_actual_single_recipient(self):
        slug = "outstanding-informational-series"
        review = review_for_year(self.decisions[slug], 1981)
        self.assertEqual(review["currentCategory"], "hosted-nonfiction-series-or-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1981/' + slug))
        winner = page["winners"][0]
        self.assertEqual(winner["heading"], "Steve Allen's Meeting of Minds")
        self.assertEqual(winner["sourceDetailLines"], ["PBS"])
        self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]], [("Loring d'Usseau", "")])
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        tribute = contexts["https://www.televisionacademy.com/features/news/hall-fame/steve-allen-hall-fame-tribute"]
        self.assertIn("devised, wrote, and hosted", tribute)
        self.assertIn("resurrected the illustrious dead", tribute)
        self.assertNotIn("Steve Allen", [c["name"] for c in winner["credits"]])

    def test_see_it_now_documentary_context_does_not_invent_presenter_awards(self):
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        for year, slug in ((1953, "best-public-affairs-program"), (1957, "best-public-service-program-or-series")):
            self.assertEqual(category_for_year(self.decisions[slug], year), "documentary-or-nonfiction-series")
            winner = next(p for p in pages if p["sourceUrl"].endswith(f"/{year}/{slug}"))["winners"][0]
            self.assertEqual(winner["sourceDetailLines"], ["CBS"])
            self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]], [("n/a", "")])
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        contract = contexts["https://www.televisionacademy.com/awards/nominees-winners/1956/outstanding-documentary-or-nonfiction-series"]
        self.assertIn("Best Documentary Program", contract)
        self.assertIn("Nominee See It Now", contract)

    def test_crusade_original_series_is_separate_from_uncertain_later_relaunch(self):
        slug = "best-public-service-program-or-series"
        self.assertEqual(category_for_year(self.decisions[slug], 1950), "documentary-or-nonfiction-series")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1950/' + slug))
        winner = page["winners"][0]
        self.assertEqual(winner["sourceDetailLines"], ["KECA-TV, KTTV"])
        self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]], [("n/a", "")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://findingaids.library.nyu.edu/nyhs/timeinc_ms3009_rg41/contents/aspace_ref131_hng/")
        self.assertIn("originally released in 1949", context)
        self.assertIn("It is unclear if this series was set to relaunch", context)
        self.assertEqual(category_for_year(self.decisions[slug], 1951), "hosted-nonfiction-series-or-special")

    def test_survivors_documentary_does_not_repair_missing_individual_roles(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1996), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1996/' + slug))
        winner = page["winners"][0]
        self.assertEqual(winner["sourceDetailLines"], ["TBS"])
        self.assertEqual([c["name"] for c in winner["credits"]],
                         ["Jacoba Atlas", "June Beallor", "Allan Holzman", "Pat Mitchell", "James Moll", "Vivian Schiller"])
        self.assertEqual([c["role"] for c in winner["credits"]], [""] * 6)
        self.assertIsNone(category_for_year(self.decisions["outstanding-individual-achievement-informational-programming"], 1996))

    def test_silvers_independent_comedian_award_retains_its_na_production_credit(self):
        self.assertEqual(category_for_year(self.decisions["best-comedian"], 1956), "lead-actor-in-a-comedy-series")
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        comedian = next(p for p in pages if p["sourceUrl"].endswith('/1956/best-comedian'))["winners"][0]
        performer = next(p for p in pages if p["sourceUrl"].endswith('/1956/best-actor'))["winners"][0]
        self.assertEqual(comedian["heading"], performer["heading"])
        self.assertEqual([p["name"] for p in comedian["programmes"]], ["N/A"])
        self.assertEqual([p["name"] for p in performer["programmes"]], ["The Phil Silvers Show"])
        self.assertNotEqual(comedian["sourceKey"], performer["sourceKey"])
        self.assertIsNone(category_for_year(self.decisions["best-comedian"], 1957))

    def test_live_tony_allocations_keep_emmy_years_and_the_main_cbs_production(self):
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        for year, slug, title in (
                (1980, "outstanding-program-achievement-special-events", "The 34th Annual Tony Awards"),
                (1998, "outstanding-variety-music-or-comedy-special", "The 1997 Tony Awards"),
                (2010, "outstanding-special-class-programs", "63rd Annual Tony Awards"),
                (2011, "outstanding-special-class-programs", "64th Annual Tony Awards"),
                (2013, "outstanding-special-class-programs", "66th Annual Tony Awards"),
                (2014, "outstanding-special-class-programs", "67th Annual Tony Awards")):
            self.assertEqual(category_for_year(self.decisions[slug], year), "variety-special-live")
            page = next(p for p in pages if p["sourceUrl"].endswith(f"/{year}/{slug}"))
            self.assertEqual(page["winners"][0]["heading"], title)
            self.assertEqual(page["winners"][0]["sourceDetailLines"], ["CBS"])
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("Broadcast live on the CBS", contexts["https://www.tonyawards.com/history/year-by-year/1997/"])
        self.assertIn("Launching the Tonys", contexts["https://www.tonyawards.com/history/year-by-year/1997/"])
        for year in (2009, 2010):
            self.assertIn("both the pre-telecast Creative Arts Awards and the Tony Awards broadcast",
                          contexts[f"https://www.tonyawards.com/history/year-by-year/{year}/"])

    def test_live_tony_history_does_not_certify_other_editions_or_red_carpet_webcasts(self):
        self.assertIsNone(category_for_year(self.decisions["outstanding-special-class-awards-programs"], 2008))
        for year in (2007,):
            self.assertIsNone(category_for_year(self.decisions["outstanding-special-class-programs"], year))
        self.assertIsNone(category_for_year(self.decisions["outstanding-program-achievement-special-events"], 1979))

    def test_omnibus_cultural_format_does_not_rewrite_its_documentary_award(self):
        self.assertEqual(category_for_year(self.decisions["outstanding-cultural-program"], 1955), "variety-series")
        self.assertEqual(category_for_year(self.decisions["outstanding-documentary-or-nonfiction-series"], 1956),
                         "documentary-or-nonfiction-series")
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("a variety show for the intellect", contexts["https://interviews.televisionacademy.com/shows/omnibus"])
        self.assertIn("on ABC in 1981", contexts["https://interviews.televisionacademy.com/shows/omnibus"])
        original = contexts["https://www.televisionacademy.com/shows/omnibus"]
        self.assertIn("Winner Best Variety Program - 1954 Omnibus CBS n/a", original)
        self.assertIn("Winner Best Documentary Program - 1956 Omnibus CBS n/a", original)

    def test_omnibus_public_service_retains_both_original_network_statements(self):
        slug = "best-public-service-program-or-series"
        pages = load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
        for year, network in ((1958, "ABC & NBC"), (1959, "NBC")):
            with self.subTest(year=year):
                self.assertEqual(category_for_year(self.decisions[slug], year), "variety-series")
                page = next(p for p in pages if p["sourceUrl"].endswith(f"/{year}/{slug}"))
                self.assertEqual(page["sourceCategory"], "Best Public Service Program Or Series")
                self.assertEqual(page["winners"][0]["sourceDetailLines"], [network])
                self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]], [("n/a", "")])

    def test_city_at_night_requires_the_actual_presenter_interview_evidence(self):
        slug = "best-public-service-program-or-series"
        decision = self.decisions[slug]
        self.assertEqual(decision["disposition"], "current-lineage")
        self.assertEqual(category_for_year(decision, 1951), "hosted-nonfiction-series-or-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1951/' + slug))
        winner = page["winners"][0]
        self.assertEqual(winner["heading"], "City at Night")
        self.assertEqual(winner["sourceDetailLines"], ["KTLA"])
        self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]], [("n/a", "")])
        url = "https://www.worldradiohistory.com/Archive-Radio-Life/50s/56/TV-Radio-Life-1956-03-02.pdf"
        record = next(s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"] if s["url"] == url)
        self.assertEqual(record["pageNumbers"], [51])
        self.assertIn("asking spontane- ous questions", record["context"])
        self.assertIn("by Ken Graue.", record["context"])
        self.assertIn(url, review_for_year(decision, 1951)["externalEvidence"])
        with self.assertRaises(SourceError):
            evidence(record, url)

    def test_raiders_documentary_is_separate_from_the_feature_and_later_extra(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1982), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1982/' + slug))
        self.assertEqual(page["winners"][0]["heading"], 'Making of "Raiders of the Lost Ark"')
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["PBS"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Sidney Ganis", ""), ("Howard Kazanjian", "")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"].startswith("https://www.lucasfilm.com/"))
        self.assertIn("(1981 documentary) The Making of Raiders of the Lost Ark", context)
        self.assertIsNone(category_for_year(self.decisions["outstanding-individual-achievement-informational-programming"], 1982))

    def test_without_pity_narration_context_does_not_repair_emmy_roles(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1997), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1997/' + slug))
        winner = page["winners"][0]
        self.assertEqual(winner["sourceDetailLines"], ["HBO"])
        self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]],
                         [("Michael Mierendorf", ""), ("Jonathan Moss", ""), ("Sheila Nevins", ""), ("Christopher Reeve", "")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"].startswith("https://dcmp.org/"))
        self.assertIn("Narrated by Christopher Reeve.", context)
        self.assertIsNone(category_for_year(self.decisions["outstanding-individual-achievement-informational-programming"], 1997))

    def test_seventieth_tony_live_telecast_keeps_delayed_pt_and_all_emmy_roles(self):
        slug = "outstanding-special-class-programs"
        self.assertEqual(category_for_year(self.decisions[slug], 2017), "variety-special-live")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/2017/' + slug))
        winner = page["winners"][0]
        self.assertEqual(winner["heading"], "70th Annual Tony Awards")
        self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]],
                         [("Ricky Kirshner", "Executive Producer"), ("Glenn Weiss", "Executive Producer"),
                          ("Allen Kelman", "Supervising Producer"), ("James Corden", "Producer/Host"),
                          ("Ben Winston", "Producer")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if '/news/tony-awards-live-stream-returns-' in s["url"])
        self.assertIn("ET/delayed PT) live from the Beacon Theatre", context)
        self.assertIsNone(category_for_year(self.decisions["outstanding-special-class-awards-programs"], 2008))

    def test_sweeney_live_title_does_not_override_the_recorded_stage_production(self):
        slug = "outstanding-special-class-programs"
        self.assertEqual(category_for_year(self.decisions[slug], 2015), "variety-special-pre-recorded")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/2015/' + slug))
        winner = page["winners"][0]
        self.assertIn("Live From Lincoln Center", winner["heading"])
        self.assertEqual(winner["sourceDetailLines"], ["PBS"])
        self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]],
                         [("Andrew Carl Wilk", "Executive Producer"), ("Allen Kelman", "Supervising Producer"),
                          ("Douglas Chang", "Producer"), ("Elizabeth W. Scott", "Produced by"), ("Audra McDonald", "Host")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"].endswith('/pbs-announces-new-fall-season-lineup/'))
        self.assertIn("staged in March 2014", context)
        self.assertIn("Friday, September 26", context)

    def test_west_wing_recording_keeps_special_class_and_all_ten_recipients(self):
        slug = "outstanding-special-class-programs"
        self.assertEqual(category_for_year(self.decisions[slug], 2002), "variety-special-pre-recorded")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/2002/' + slug))
        self.assertEqual(page["sourceCategory"], "Outstanding Special Class Program")
        winner = page["winners"][0]
        self.assertEqual(winner["heading"], "The West Wing: Documentary Special")
        self.assertEqual(winner["sourceDetailLines"], ["NBC"])
        self.assertEqual([c["name"] for c in winner["credits"]],
                         ["Eli Attie", "William Couturie", "Kevin Falls", "Michael Hissrich", "Anne Sandkuhler",
                          "Thomas Schlamme", "Aaron Sorkin", "John Wells", "Llewellyn Wells", "Felicia Willson"])
        self.assertEqual(next(c["role"] for c in winner["credits"] if c["name"] == "William Couturie"), "")
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"].startswith("https://billzarchy.com/"))
        self.assertIn("During 11 shooting days", context)
        self.assertIn("completes postproduction in Hollywood", context)

    def test_victory_at_sea_original_documentary_is_not_the_naval_memoir(self):
        decision = self.decisions["best-public-affairs-program"]
        self.assertEqual(decision["disposition"], "current-lineage")
        self.assertEqual(category_for_year(decision, 1954), "documentary-or-nonfiction-series")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1954/best-public-affairs-program'))
        winner = page["winners"][0]
        self.assertEqual(winner["heading"], "Victory at Sea")
        self.assertEqual(winner["sourceDetailLines"], ["NBC"])
        self.assertEqual([(c["name"], c["role"]) for c in winner["credits"]], [("n/a", "")])
        url = "https://www.history.navy.mil/about-us/leadership/director/directors-corner/h-grams/h-gram-003.html"
        record = next(s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"] if s["url"] == url)
        self.assertIn('26-episode', record["context"])
        self.assertIn('television documentary from the early 1950', record["context"])
        with self.assertRaises(SourceError):
            evidence(record, url)

    def test_benny_broad_personality_award_does_not_replace_his_character_acting_award(self):
        decision = self.decisions["best-comedian"]
        review = review_for_year(decision, 1958)
        self.assertEqual(review["disposition"], "excluded")
        self.assertNotIn("currentCategory", review)
        self.assertIsNone(category_for_year(decision, 1958))
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1958/best-comedian'))
        winner = page["winners"][0]
        self.assertIn("Any Person Who Essentially Plays Himself", page["sourceCategory"])
        self.assertEqual(winner["heading"], "Jack Benny")
        self.assertEqual([p["name"] for p in winner["programmes"]], ["The Jack Benny Show"])
        self.assertEqual(review["reviewedSourcePages"][0]["winnerSourceKeys"], [winner["sourceKey"]])
        self.assertEqual(category_for_year(self.decisions["outstanding-lead-actor-in-a-comedy-series"], 1959),
                         "lead-actor-in-a-comedy-series")

    def test_baseball_tv_nation_tie_keeps_original_nbc_programme_and_unavailable_roles(self):
        slug = "outstanding-informational-series"
        decision = self.decisions[slug]
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1995/' + slug))
        self.assertIsNone(category_for_year(decision, 1995))
        self.assertEqual([category_for_winner(decision, 1995, w["sourceKey"]) for w in page["winners"]],
                         ["documentary-or-nonfiction-series", "hosted-nonfiction-series-or-special"])
        baseball, tv_nation = page["winners"]
        self.assertEqual(baseball["heading"], "Baseball (A General Motors Mark Of Excellence Pres")
        self.assertEqual(tv_nation["heading"], "TV Nation")
        self.assertEqual([w["sourceDetailLines"] for w in page["winners"]], [["PBS"], ["NBC"]])
        self.assertEqual([[c["name"] for c in w["credits"]] for w in page["winners"]], [
            ["Ken Burns", "John Chancellor", "Lynn Novick", "Geoffrey C. Ward"],
            ["Randy Cohen", "Kathleen Glynn", "Chris Kelly", "Jerry Kupfer", "Michael Moore",
             "Stephen Sherrill", "David Wald", "Eric Zicklin"]])
        self.assertTrue(all(c["role"] == "" for w in page["winners"] for c in w["credits"]))
        contexts = {s["url"]: s for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("nine-part documentary series Baseball debuted in 1994",
                      contexts["https://www.pbs.org/kenburns/baseball/about"]["context"])
        self.assertIn("The Tenth Inning , a two-part", contexts[
            "https://www.pbs.org/kenburns/baseball/about"]["context"])
        original = contexts["https://www.congress.gov/103/crecb/1994/05/10/GPO-CRECB-1994-pt7-7-1.pdf"]
        self.assertEqual(original["pageNumbers"], [5])
        self.assertIn("May 10, 1994", original["context"])
        self.assertIn("view with Michael Moore, the host of", original["context"])
        # The source's original PDF line break/soft hyphen is retained.
        self.assertIn("inter\u00ad\nview", original["context"])

    def test_biography_great_war_tie_preserves_the_presenter_and_documentary_formats(self):
        slug = "outstanding-informational-series"
        decision = self.decisions[slug]
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1997/' + slug))
        self.assertIsNone(category_for_year(decision, 1997))
        self.assertEqual({w["heading"]: category_for_winner(decision, 1997, w["sourceKey"])
                          for w in page["winners"]}, {
            "Biography": "hosted-nonfiction-series-or-special",
            "The Great War And The Shaping Of The 20th Century": "documentary-or-nonfiction-series"})
        self.assertEqual(page["sourceCategory"], "Outstanding Informational Series")
        self.assertEqual([w["sourceDetailLines"] for w in page["winners"]], [["A&E"], ["PBS"]])
        self.assertEqual([[c["name"] for c in w["credits"]] for w in page["winners"]], [
            ["Michael Cascio", "Carol Anne Dolan", "Diane Ferenczi", "Peter Graves", "Jack Perkins"],
            ["Blaine Baggett", "Carl Byker", "Jay Winter"]])
        self.assertTrue(all(c["role"] == "" for w in page["winners"] for c in w["credits"]))
        review = review_for_year(decision, 1997)
        self.assertEqual([a["sourceKey"] for a in review["winnerAllocations"]],
                         [w["sourceKey"] for w in page["winners"]])
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("which he hosted from 1994 to 1999", contexts[
            "https://www.televisionacademy.com/bios/jack-perkins"])
        self.assertIn("In eight stirring parts", contexts[
            "https://peabodyawards.com/award-profile/the-great-war-and-the-shaping-of-the-20th-century/"])

    def test_broadway_fosse_tie_keeps_producer_award_and_empty_recipient_list(self):
        slug = "outstanding-informational-special"
        decision = self.decisions[slug]
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1990/' + slug))
        self.assertIsNone(category_for_year(decision, 1990))
        self.assertEqual([category_for_winner(decision, 1990, w["sourceKey"]) for w in page["winners"]],
                         ["hosted-nonfiction-series-or-special", "documentary-or-nonfiction-special"])
        broadway, fosse = page["winners"]
        self.assertEqual(broadway["heading"], "Broadway's Dreamers: The Legacy Of The Group Theat")
        self.assertEqual([(c["name"], c["role"]) for c in broadway["credits"]], [
            ("Joanne Woodward", "Producer"), ("David Heeley", "Producer"), ("Joan Kramer", "Producer"),
            ("Susan Lacy", "Executive Producer"), ("Jac Venza", "Executive Producer")])
        self.assertEqual(fosse["heading"], "Dance In America: Bob Fosse Steam Heat Great Perfo")
        self.assertEqual(fosse["credits"], [])
        self.assertEqual([w["sourceDetailLines"] for w in page["winners"]], [["PBS"], ["PBS"]])
        review = review_for_year(decision, 1990)
        self.assertEqual([a["sourceKey"] for a in review["winnerAllocations"]],
                         [w["sourceKey"] for w in page["winners"]])
        contexts = {s["url"]: s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        self.assertIn("hosts the program and interviews Mesiner", contexts[
            "https://americanarchive.org/catalog/cpb-aacip_75-41zcrzgc"])
        self.assertIn("Premiere: 6/26/1989", contexts[
            "https://www.pbs.org/wnet/americanmasters/group-theatre-about-the-group-theatre/622/"])
        self.assertIn("PBS documentary on Bob Fosse", contexts[
            "https://www.pbs.org/wnet/americanmasters/archive/interview/richard-adler/"])

    def test_fields_documentary_account_does_not_supply_missing_emmy_roles(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1986), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1986/' + slug))
        self.assertEqual(page["winners"][0]["heading"], "W.C. Fields Straight Up")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["PBS"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Ronald J. Fields", ""), ("Robert B. Weide", "")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://www.duckprods.com/projects/wcfields/index.html")
        self.assertIn("documentary on W.C. Fields", context)
        self.assertIn("broadcast on PBS in March of 1986", context)

    def test_dear_america_original_real_footage_is_not_scripted_acting_or_writing_awards(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1988), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1988/' + slug))
        self.assertEqual(page["winners"][0]["heading"], "Dear America: Letters Home from Vietnam")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["HBO"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Thomas Bird", ""), ("Bill Couturie", "")])
        self.assertIsNone(category_for_year(self.decisions[
            "outstanding-individual-achievement-informational-programming"], 1988))
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://catalog.afi.com/Film/57599-DEAR-AMERICALETTERSHOMEFROMVIETNAM")
        self.assertIn("( 1987 )", context)
        self.assertIn("nothing has been re-enacted", context)

    def test_whale_production_narration_does_not_create_a_narrator_emmy(self):
        slug = "outstanding-informational-special"
        self.assertEqual(category_for_year(self.decisions[slug], 1978), "documentary-or-nonfiction-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1978/' + slug))
        self.assertEqual(page["winners"][0]["heading"], "The Great Whales National Geographic")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["PBS"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Dennis B. Kane", ""), ("Nicholas Noxon", ""), ("Thomas Skinner", "")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://americanarchive.org/catalog/cpb-aacip-526-251fj2bb0n")
        self.assertIn("film footage of the birth of a killer whale", context)
        self.assertIn("Broadcast Date 1978-02-16", context)
        self.assertIn("Narrator: Scourby, Alexander", context)

    def test_brooks_honorary_gala_keeps_its_recorded_variety_programme_emmy(self):
        slug = "outstanding-variety-music-or-comedy-special"
        self.assertEqual(category_for_year(self.decisions[slug], 2014), "variety-special-pre-recorded")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/2014/' + slug))
        self.assertEqual(page["sourceCategory"], "Outstanding Variety Special")
        self.assertEqual(page["winners"][0]["heading"], "AFI Life Achievement Award: A Tribute To Mel Brooks")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], ["TNT"])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]], [
            ("Bob Gazzale", "Executive Producer"), ("Cort Casady", "Supervising Producer"),
            ("Chris Merrill", "Producer"), ("Martin Short", "Performer / Host")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://www.afi.com/press/afi_laa_2013_brooks/")
        self.assertIn("June 7, 2013", context)
        self.assertIn("gala was taped", context)
        self.assertIn("will premiere on Saturday, June 15", context)

    def test_heroes_live_telethon_context_does_not_fill_absent_academy_network_evidence(self):
        slug = "outstanding-variety-music-or-comedy-special"
        self.assertEqual(category_for_year(self.decisions[slug], 2002), "variety-special-live")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/2002/' + slug))
        self.assertEqual(page["winners"][0]["heading"], "America: A Tribute To Heroes")
        self.assertEqual(page["winners"][0]["sourceDetailLines"], [])
        self.assertEqual([(c["name"], c["role"]) for c in page["winners"][0]["credits"]],
                         [("Joel Gallen", "Executive Producer")])
        context = next(s["context"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]
                       if s["url"] == "https://peabodyawards.com/award-profile/america-a-tribute-to-heroes/")
        self.assertIn("carried live, commercial free", context)

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
        contexts = {s["url"] for s in load(SOURCE_DIR / "lineage-decisions.json")["contextSources"]}
        for slug, year, targets in (
                ("outstanding-writing-for-a-variety-series", 1990,
                 {"writing-for-a-variety-series", "writing-for-a-variety-special"}),
                ("outstanding-informational-series", 1997,
                 {"hosted-nonfiction-series-or-special", "documentary-or-nonfiction-series"}),
                ("outstanding-informational-series", 1995,
                 {"hosted-nonfiction-series-or-special", "documentary-or-nonfiction-series"}),
                ("outstanding-informational-special", 1990,
                 {"hosted-nonfiction-series-or-special", "documentary-or-nonfiction-special"})):
            decision = self.decisions[slug]
            review = deepcopy(review_for_year(decision, year))
            review["winnerAllocations"].pop()
            pages = {p["sourceUrl"]: p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                     if p["year"] in review["years"] and p["sourceUrl"].endswith('/' + slug)}
            with self.subTest(slug=slug), self.assertRaisesRegex(SourceError, "allocate every winner exactly once"):
                validate_review(review, {p["year"]: u for u, p in pages.items()},
                                {u: (p["year"], slug) for u, p in pages.items()}, pages, targets, contexts)

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
        self.assertIsNone(category_for_year(decision, 1954))
        self.assertEqual(category_for_year(decision, 1955), "hosted-nonfiction-series-or-special")
        page = next(p for p in load(SOURCE_DIR / "official-winners-1949-2026.json")["pages"]
                    if p["sourceUrl"].endswith('/1954/' + decision["sourceSlug"]))
        self.assertEqual({w["heading"] for w in page["winners"]}, {"What's My Line?", "This Is Your Life"})
        targets = {w["heading"]: category_for_winner(decision, 1954, w["sourceKey"]) for w in page["winners"]}
        self.assertEqual(targets, {"What's My Line?": "game-show",
                                  "This Is Your Life": "hosted-nonfiction-series-or-special"})
        # Both sides of the original tie survive; the page-wide category
        # remains deliberately unset because their actual formats differ.
        self.assertEqual(len(review_for_year(decision, 1954)["winnerAllocations"]), 2)

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
