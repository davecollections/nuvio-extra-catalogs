"""Pure unit checks for identity conflicts and edition-specific artwork guards."""

import unittest
from unittest.mock import patch

from audit_awards_work_mappings import flags, review_basis, validate_review
from bafta_artwork import ArtworkError, reviewed_season_posters, tmdb_fallback
from enrich_bafta_identities import apply_overrides, validate_overrides
from bafta_outputs import OutputError, reviewed_tvdb_posters, build_outputs, TELEVISION_CONFIG
from enrich_golden_globes_identities import IdentityError


class WorkMappingTests(unittest.TestCase):
    def test_sports_title_year_match_needs_production_review(self):
        entry = {"key": "television:sport:2001", "categoryIds": ["television-sports-coverage"],
                 "resolution": {"method": "tmdb-exact-title-media-and-award-window"}}
        with patch("enrich_bafta_identities.load_overrides", return_value={"works": [], "omissions": []}):
            with self.assertRaises(IdentityError):
                validate_overrides({"works": [entry]})

    def setUp(self):
        self.entry = {"imdbId": "tt123", "mediaType": "series", "tmdbIds": [1],
                      "titles": ["Example"], "releaseYears": [2000], "awardYears": [2001]}
        self.evidence = {"mapped": [{"imdbId": "tt123", "title": "Example", "originalTitle": "Example",
                                   "alternativeTitles": [], "releaseDate": "2000-01-01"}],
                         "externalLookup": [{"mediaType": "series", "tmdbId": 1}],
                         "posters": [{"status": 200, "contentType": "image/jpeg"}]}

    def test_working_poster_does_not_hide_wrong_imdb_id(self):
        self.evidence["mapped"][0]["imdbId"] = "tt999"
        self.assertIn("tmdb-imdb-conflict", flags(self.entry, self.evidence))

    def test_matching_ids_and_poster_do_not_confirm_awarded_production(self):
        self.entry["productionContexts"] = [{"creditNames": ["Awarded Director"],
            "method": "tmdb-exact-title-media-and-award-window"}]
        self.evidence["mapped"][0]["production"] = {
            "credits": [{"name": "Different Director"}], "creators": []}
        self.assertIn("production-credit-review", flags(self.entry, self.evidence))
        self.evidence["mapped"][0]["production"]["credits"] = [{"name": "Awarded Director"}]
        self.assertNotIn("production-credit-review", flags(self.entry, self.evidence))

    def test_generic_credit_does_not_certify_automatic_title_match(self):
        self.entry["productionContexts"] = [{"creditNames": ["Production Team"],
            "method": "tmdb-exact-title-media-and-award-window"}]
        self.evidence["mapped"][0]["production"] = {"credits": [], "creators": []}
        self.assertIn("production-without-named-credits-review", flags(self.entry, self.evidence))

    def test_missing_production_response_cannot_silently_pass(self):
        self.entry["productionContexts"] = [{"creditNames": ["Director"], "method": "reviewed-manual-override"}]
        self.assertIn("production-evidence-missing", flags(self.entry, self.evidence))

    def test_pending_credit_check_cannot_approve_identity_conflict(self):
        row = {"inventory": self.entry, "evidence": self.evidence,
               "flags": ["production-credit-review"]}
        row["review"] = {"basisSha256": review_basis(row), "flagNotes": {},
                         "pendingFlags": ["production-credit-review"]}
        validate_review("series:tt123", row)
        row["flags"] = ["tmdb-imdb-conflict"]
        row["review"] = {"basisSha256": review_basis(row), "flagNotes": {},
                         "pendingFlags": ["tmdb-imdb-conflict"]}
        with self.assertRaises(ValueError):
            validate_review("series:tt123", row)

    def test_episode_lookup_does_not_confirm_series(self):
        self.evidence["externalLookup"] = [{"mediaType": "tv_episode", "tmdbId": 1}]
        self.assertIn("external-lookup-media-review", flags(self.entry, self.evidence))

    def test_changed_evidence_invalidates_review(self):
        self.evidence["mapped"][0]["imdbId"] = None
        row = {"inventory": self.entry, "evidence": self.evidence, "flags": flags(self.entry, self.evidence)}
        row["review"] = {"basisSha256": review_basis(row), "flagNotes": {f: "Reviewed exception" for f in row["flags"]}}
        validate_review("series:tt123", row)
        row["evidence"]["mapped"][0]["imdbId"] = "tt999"
        with self.assertRaises(ValueError):
            validate_review("series:tt123", row)

    def test_canonical_date_after_award_is_visible_without_tmdb(self):
        self.entry["tmdbIds"] = []
        self.entry["releaseYears"] = [2005]
        self.evidence["mapped"] = []
        self.assertIn("canonical-release-after-award-review", flags(self.entry, self.evidence))


class SeasonPosterTests(unittest.TestCase):
    def setUp(self):
        self.source = {"tmdbId": 12, "seasonNumber": 3, "seasonTitle": "Festival 2000", "releaseYear": 2000,
                       "reviewNote": "Matched the named annual broadcast", "evidenceUrls": ["https://example.org/review"]}
        self.identity = {"mediaType": "series", "tmdbId": None}

    def test_matching_edition_does_not_invent_work_mapping(self):
        with patch("bafta_artwork.api_json", return_value={"name": "Festival 2000", "air_date": "2000-06-01", "poster_path": "/poster.jpg"}):
            result = tmdb_fallback("tt123", self.identity, "unit-test", self.source)
        self.assertIsNone(result["tmdbId"])
        self.assertEqual(result["reviewedSeasonPoster"], self.source)
        self.assertTrue(result["posterUrl"].endswith("/poster.jpg"))

    def test_wrong_edition_is_rejected(self):
        for title, date in [("Festival 1999", "2000-06-01"), ("Festival 2000", "1999-06-01")]:
            with self.subTest(title=title, date=date), patch("bafta_artwork.api_json", return_value={"name": title, "air_date": date, "poster_path": "/poster.jpg"}):
                with self.assertRaises(ArtworkError):
                    tmdb_fallback("tt123", self.identity, "unit-test", self.source)

    def test_season_source_cannot_attach_to_movie(self):
        with self.assertRaises(ArtworkError):
            reviewed_season_posters({"reviewedSeasonPosters": {"tt123": self.source}},
                                   {"tt123": {"mediaType": "movie", "title": "Festival 2000"}})


class ReviewedDateTests(unittest.TestCase):
    def test_reviewed_production_replaces_same_named_tmdb_film(self):
        override = {"key": "television:ourland:2022", "mediaType": "movie",
                    "imdbId": "tt19268738", "title": "Our Land", "releaseYear": 2021,
                    "reviewNote": "BAFTA credits Genova and Thirolle, not Mwepu's Swedish drama.",
                    "evidenceUrls": ["https://www.alfredthirolle.com/portfolio/our-land-1"]}
        identity_map = {"works": [{"key": override["key"], "resolution": {
            "mediaType": "movie", "tmdbId": 780046, "imdbId": "tt13649306",
            "title": "Our Land", "releaseYear": 2020}}]}
        with patch("enrich_bafta_identities.load_overrides", return_value={"works": [override], "omissions": []}), patch("enrich_bafta_identities.api_json") as api:
            apply_overrides(identity_map)
            validate_overrides(identity_map)
            api.assert_not_called()
        resolution = identity_map["works"][0]["resolution"]
        self.assertEqual(resolution["imdbId"], "tt19268738")
        self.assertNotIn("tmdbId", resolution)

    def test_broadcast_year_survives_reusing_tmdb_dvd_record(self):
        override = {"key": "television:example:2001", "mediaType": "series", "tmdbId": 1,
                    "imdbId": "tt123", "title": "Example", "releaseYear": 2000,
                    "reviewNote": "Verified original broadcast; TMDB dates a later DVD release.",
                    "evidenceUrls": ["https://example.org/broadcast"]}
        payload = {"works": [override], "omissions": []}
        identity_map = {"works": [{"key": override["key"], "resolution": {
            "mediaType": "series", "tmdbId": 1, "imdbId": "tt123", "title": "Example DVD",
            "releaseYear": 2005, "method": "reviewed-manual-override"}}]}
        with patch("enrich_bafta_identities.load_overrides", return_value=payload), patch("enrich_bafta_identities.api_json") as api:
            apply_overrides(identity_map)
            validate_overrides(identity_map)
            api.assert_not_called()
        self.assertEqual(identity_map["works"][0]["resolution"]["releaseYear"], 2000)
        self.assertEqual(identity_map["works"][0]["resolution"]["title"], "Example")


class TvdbPosterTests(unittest.TestCase):
    def test_poster_from_different_series_is_rejected(self):
        source = {"tvdbId": 12, "posterUrl": "https://artworks.thetvdb.com/banners/series/99/posters/abc.jpg",
                  "reviewNote": "Reviewed", "evidenceUrls": ["https://thetvdb.com/series/example", "https://www.imdb.com/title/tt123/"]}
        with self.assertRaises(OutputError):
            reviewed_tvdb_posters({"reviewedTvdbPosters": {"tt123": source}})

    def test_missing_imdb_evidence_is_rejected(self):
        source = {"tvdbId": 12, "posterUrl": "https://artworks.thetvdb.com/banners/series/12/posters/abc.jpg",
                  "reviewNote": "Reviewed", "evidenceUrls": ["https://thetvdb.com/series/example"]}
        with self.assertRaises(OutputError):
            reviewed_tvdb_posters({"reviewedTvdbPosters": {"tt123": source}})


class RetainedCatalogueTests(unittest.TestCase):
    def test_correction_keeps_empty_movie_route_and_valid_series(self):
        import json
        category = "television-sports-coverage"
        movie = {"mediaType": "movie", "id": "retained-films", "name": "Films",
                 "expectedWorkLinks": 0, "expectedItems": 0,
                 "emptyCatalogueReason": "Preserve the released route after correcting wrong productions."}
        series = {"mediaType": "series", "id": "sports-series", "name": "Series",
                  "expectedWorkLinks": 1, "expectedItems": 1}
        contract = {"awardBodyId": TELEVISION_CONFIG.award_body_id, "categories": [{
            "categoryId": category, "firstCeremony": 1, "lastCeremony": 1,
            "expectedResults": 1, "expectedWorkLinks": 1, "catalogs": [movie, series]}]}
        rows = {category: [{"ceremony": 1, "resultIndex": 0, "workIndex": 0,
                            "work": {"mediaType": "series", "title": "Reviewed broadcast", "imdbId": "tt123"}}]}
        with patch("bafta_outputs.collect_rows", return_value=(rows, {category: 1}, {category})), patch("bafta_outputs.load_json", return_value=contract):
            outputs, manifest = build_outputs(TELEVISION_CONFIG)
            self.assertEqual(len(manifest), 2)
            self.assertEqual(json.loads(next(v for p, v in outputs.items() if p.stem == "retained-films")), {"metas": []})
            movie.pop("emptyCatalogueReason")
            with self.assertRaises(OutputError):
                build_outputs(TELEVISION_CONFIG)

if __name__ == "__main__":
    unittest.main()
