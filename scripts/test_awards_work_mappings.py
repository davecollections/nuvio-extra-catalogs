"""Pure unit checks for identity conflicts and edition-specific artwork guards."""

import unittest
from unittest.mock import patch

from audit_awards_work_mappings import flags, review_basis, validate_review
from bafta_artwork import ArtworkError, reviewed_season_posters, tmdb_fallback
from enrich_bafta_identities import apply_overrides, validate_overrides
from bafta_outputs import OutputError, reviewed_tvdb_posters


class WorkMappingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
