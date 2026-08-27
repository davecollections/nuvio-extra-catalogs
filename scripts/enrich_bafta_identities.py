#!/usr/bin/env python3
"""Enrich and validate the reviewed BAFTA identity inventory.

The committed BAFTA snapshots decide award facts. TMDB is used only during a
reviewed maintenance run to propose or attach stable work identities. Offline
generation consumes the committed identity map and never needs API credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from bafta_common import ROOT, SOURCE_DIR, identity_in_current_programme, load_json
from enrich_golden_globes_identities import (
    IdentityError,
    candidate_titles,
    clean_text,
    normalized_title,
    title_variants as shared_title_variants,
    tmdb_json,
)


IDENTITY_MAP_PATH = SOURCE_DIR / "identity-map.json"
OVERRIDES_PATH = SOURCE_DIR / "identity-overrides.json"
TOKEN_ENV = "TMDB_API_READ_TOKEN"
IMDB_TITLE_RE = re.compile(r"tt\d+")
ALTERNATE_TITLE_RE = re.compile(r"^(?P<title>.+?)\s*\((?P<alternate>[^()]+)\)\s*$")
CANONICAL_RESULTS_ROOT = ROOT / "data" / "awards"


def api_json(path: str, token: str, params: dict | None = None) -> dict:
    """Reuse the established TMDB client with bounded transient retries."""
    last_error: IdentityError | None = None
    for attempt in range(3):
        try:
            return tmdb_json(path, token, params)
        except IdentityError as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.75 * (2**attempt))
    assert last_error is not None
    raise last_error


def year_from(value: object) -> int | None:
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def title_variants(value: str) -> list[str]:
    """Add reviewed BAFTA display-title forms to the shared query variants."""
    variants = shared_title_variants(value)
    match = ALTERNATE_TITLE_RE.fullmatch(clean_text(value))
    if match:
        for part in (match.group("title"), match.group("alternate")):
            cleaned = clean_text(part)
            if cleaned and cleaned not in variants:
                variants.append(cleaned)
    for variant in list(variants):
        if variant.casefold().startswith("the ") and len(variant) > 4:
            without_article = variant[4:]
            if without_article not in variants:
                variants.append(without_article)
    return variants


def allowed_media(entry: dict, candidate: dict) -> bool:
    media_type = candidate.get("media_type")
    if entry.get("mediaScope") == "movie":
        return media_type == "movie"
    return media_type in {"movie", "tv"}


def exact_title(entry: dict, candidate: dict) -> bool:
    expected = {
        normalized_title(variant)
        for title in entry.get("titles", [])
        for variant in title_variants(title)
    }
    actual = {normalized_title(title) for title in candidate_titles(candidate)}
    return bool(expected & actual)


def rough_rank(entry: dict, candidate: dict) -> tuple:
    award_year = entry["years"][0]
    media_type = candidate.get("media_type")
    release_year = year_from(
        candidate.get("release_date") if media_type == "movie" else candidate.get("first_air_date")
    )
    if release_year is None or release_year > award_year:
        distance = 999
    else:
        distance = award_year - release_year
    popularity = candidate.get("popularity") or 0
    return (-distance, popularity)


def candidate_details(entry: dict, candidate: dict, token: str) -> dict:
    tmdb_type = candidate["media_type"]
    details = api_json(
        f"/{tmdb_type}/{candidate['id']}",
        token,
        {"append_to_response": "external_ids", "language": "en-US"},
    )
    release_year = year_from(
        details.get("release_date") if tmdb_type == "movie" else details.get("first_air_date")
    )
    last_air_year = year_from(details.get("last_air_date")) if tmdb_type == "tv" else None
    imdb_id = details.get("external_ids", {}).get("imdb_id") or details.get("imdb_id")
    if not isinstance(imdb_id, str) or not IMDB_TITLE_RE.fullmatch(imdb_id):
        imdb_id = None
    award_year = entry["years"][0]
    if tmdb_type == "movie":
        plausible = (
            release_year is not None
            and release_year <= award_year
            and award_year - release_year <= 3
        )
    else:
        plausible = (
            release_year is not None
            and release_year <= award_year
            and last_air_year is not None
            and last_air_year >= award_year - 2
        )
    return {
        "mediaType": "series" if tmdb_type == "tv" else "movie",
        "tmdbId": candidate["id"],
        "title": clean_text(details.get("name") or details.get("title") or entry["titles"][0]),
        "originalTitle": clean_text(
            details.get("original_name")
            or details.get("original_title")
            or details.get("name")
            or details.get("title")
            or entry["titles"][0]
        ),
        **({"releaseYear": release_year} if release_year is not None else {}),
        **({"lastAirYear": last_air_year} if last_air_year is not None else {}),
        **({"imdbId": imdb_id} if imdb_id is not None else {}),
        "awardWindowPlausible": plausible,
        "popularity": candidate.get("popularity") or 0,
    }


def resolution_from(candidate: dict) -> dict:
    return {
        "mediaType": candidate["mediaType"],
        "title": candidate["title"],
        **(
            {"releaseYear": candidate["releaseYear"]}
            if "releaseYear" in candidate
            else {}
        ),
        "tmdbId": candidate["tmdbId"],
        "imdbId": candidate["imdbId"],
        "method": "tmdb-exact-title-media-and-award-window",
    }


def enrich_work(entry: dict, token: str) -> tuple[str, dict | None, list[dict]]:
    candidates_by_id: dict[tuple[str, int], dict] = {}
    for title in entry.get("titles", []):
        for query in title_variants(title):
            payload = api_json(
                "/search/multi",
                token,
                {"query": query, "include_adult": "false", "language": "en-US", "page": 1},
            )
            for candidate in payload.get("results", []):
                candidate_id = candidate.get("id")
                if (
                    isinstance(candidate_id, int)
                    and allowed_media(entry, candidate)
                    and exact_title(entry, candidate)
                ):
                    candidates_by_id[(candidate["media_type"], candidate_id)] = candidate
            if candidates_by_id:
                break
        if candidates_by_id:
            break

    ranked = sorted(
        candidates_by_id.values(),
        key=lambda candidate: rough_rank(entry, candidate),
        reverse=True,
    )[:8]
    reviewed = [candidate_details(entry, candidate, token) for candidate in ranked]
    plausible = [
        candidate
        for candidate in reviewed
        if candidate.get("awardWindowPlausible") and candidate.get("imdbId")
    ]
    resolution = resolution_from(plausible[0]) if len(plausible) == 1 else None
    return entry["key"], resolution, reviewed


def enrich_works(
    identity_map: dict,
    workers: int,
    offset: int,
    limit: int | None,
    retry_candidates: bool,
    programme: str | None,
) -> None:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise IdentityError(f"{TOKEN_ENV} is required for --tmdb")
    pending = [
        entry
        for entry in identity_map["works"]
        if "resolution" not in entry
        and (programme is None or identity_in_current_programme(entry, programme))
        and (retry_candidates or "candidates" not in entry)
    ]
    pending = pending[offset : offset + limit if limit is not None else None]
    results: dict[str, tuple[dict | None, list[dict]]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(enrich_work, entry, token): entry for entry in pending}
        for future in as_completed(futures):
            key, resolution, candidates = future.result()
            results[key] = (resolution, candidates)
    for entry in identity_map["works"]:
        result = results.get(entry["key"])
        if result is None:
            continue
        resolution, candidates = result
        if resolution is not None:
            entry["resolution"] = resolution
            entry.pop("candidates", None)
        else:
            entry["candidates"] = candidates


def canonical_work_index() -> dict[str, dict[tuple[str, int, str], dict]]:
    index: dict[str, dict[tuple[str, int, str], dict]] = {}
    for path in sorted(CANONICAL_RESULTS_ROOT.glob("*/results/*.json")):
        payload = load_json(path)
        if payload.get("awardBodyId") == "bafta":
            continue
        for result in payload.get("results", []):
            work = result.get("work")
            if not isinstance(work, dict):
                continue
            media_type = work.get("mediaType")
            tmdb_id = work.get("tmdbId")
            imdb_id = work.get("imdbId")
            title = work.get("title")
            release_year = work.get("releaseYear")
            if (
                media_type not in {"movie", "series"}
                or not isinstance(tmdb_id, int)
                or tmdb_id <= 0
                or not isinstance(imdb_id, str)
                or not IMDB_TITLE_RE.fullmatch(imdb_id)
                or not isinstance(title, str)
                or not title.strip()
                or not isinstance(release_year, int)
            ):
                continue
            identity = (media_type, tmdb_id, imdb_id)
            index.setdefault(normalized_title(title), {})[identity] = {
                "mediaType": media_type,
                "title": clean_text(title),
                "releaseYear": release_year,
                "tmdbId": tmdb_id,
                "imdbId": imdb_id,
                "method": "existing-canonical-awards-reuse",
            }
    return index


def reuse_canonical_works(identity_map: dict) -> int:
    canonical = canonical_work_index()
    reused = 0
    for entry in identity_map["works"]:
        if "resolution" in entry:
            continue
        candidates = entry.get("candidates", [])
        candidate_identities = {
            (candidate["mediaType"], candidate["tmdbId"], candidate.get("imdbId"))
            for candidate in candidates
            if candidate.get("awardWindowPlausible") and candidate.get("imdbId")
        }
        matches: dict[tuple[str, int, str], dict] = {}
        for title in entry.get("titles", []):
            for identity, resolution in canonical.get(normalized_title(title), {}).items():
                if entry.get("mediaScope") == "movie" and resolution["mediaType"] != "movie":
                    continue
                if identity in candidate_identities:
                    matches[identity] = resolution
        if len(matches) != 1:
            continue
        entry["resolution"] = next(iter(matches.values()))
        entry.pop("candidates", None)
        reused += 1
    return reused


def load_overrides() -> dict:
    payload = load_json(OVERRIDES_PATH)
    if set(payload) != {"schemaVersion", "awardBodyId", "works", "omissions"}:
        raise IdentityError(f"{OVERRIDES_PATH}: invalid top-level keys")
    if payload["schemaVersion"] != 1 or payload["awardBodyId"] != "bafta":
        raise IdentityError(f"{OVERRIDES_PATH}: invalid identity-override contract")
    if not isinstance(payload["works"], list) or not isinstance(payload["omissions"], list):
        raise IdentityError(f"{OVERRIDES_PATH}: works and omissions must be arrays")
    return payload


def apply_overrides(identity_map: dict) -> tuple[int, int]:
    payload = load_overrides()
    token = os.environ.get(TOKEN_ENV)
    by_key = {entry["key"]: entry for entry in identity_map["works"]}
    applied = 0
    omitted = 0
    for override in payload["works"]:
        key = override["key"]
        entry = by_key.get(key)
        if entry is None:
            raise IdentityError(f"{OVERRIDES_PATH}: unknown work key {key!r}")
        media_type = override["mediaType"]
        tmdb_id = override.get("tmdbId")
        if tmdb_id is not None:
            existing = entry.get("resolution")
            if (
                isinstance(existing, dict)
                and existing.get("method") == "reviewed-manual-override"
                and existing.get("mediaType") == media_type
                and existing.get("tmdbId") == tmdb_id
                and (
                    "imdbId" not in override
                    or existing.get("imdbId") == override["imdbId"]
                )
            ):
                resolution = existing
                entry["resolution"] = resolution
                entry["reviewNote"] = override["reviewNote"]
                entry.pop("candidates", None)
                entry.pop("reviewOutcome", None)
                applied += 1
                continue
            if not token:
                raise IdentityError(
                    f"{TOKEN_ENV} is required to refresh TMDB override {key}"
                )
            tmdb_type = "tv" if media_type == "series" else "movie"
            details = api_json(
                f"/{tmdb_type}/{tmdb_id}",
                token,
                {"append_to_response": "external_ids", "language": "en-US"},
            )
            tmdb_imdb_id = details.get("external_ids", {}).get("imdb_id") or details.get(
                "imdb_id"
            )
            override_imdb_id = override.get("imdbId")
            if tmdb_imdb_id and override_imdb_id and tmdb_imdb_id != override_imdb_id:
                raise IdentityError(
                    f"{OVERRIDES_PATH}: IMDb ID for {key} conflicts with TMDB {tmdb_type}/{tmdb_id}"
                )
            imdb_id = tmdb_imdb_id or override_imdb_id
            if not isinstance(imdb_id, str) or not IMDB_TITLE_RE.fullmatch(imdb_id):
                raise IdentityError(f"TMDB {tmdb_type}/{tmdb_id} has no reviewed IMDb ID")
            release_value = (
                details.get("first_air_date")
                if media_type == "series"
                else details.get("release_date")
            )
            release_year = year_from(release_value)
            if release_year is None:
                raise IdentityError(f"TMDB {tmdb_type}/{tmdb_id} has no release year")
            resolution = {
                "mediaType": media_type,
                "title": clean_text(
                    details.get("name") or details.get("title") or entry["titles"][0]
                ),
                "releaseYear": release_year,
                "tmdbId": tmdb_id,
                "imdbId": imdb_id,
                "method": "reviewed-manual-override",
            }
        else:
            resolution = {
                "mediaType": media_type,
                "title": clean_text(override.get("title") or entry["titles"][0]),
                "releaseYear": override["releaseYear"],
                "imdbId": override["imdbId"],
                "method": "reviewed-imdb-override",
            }
        entry["resolution"] = resolution
        entry["reviewNote"] = override["reviewNote"]
        entry.pop("candidates", None)
        entry.pop("reviewOutcome", None)
        applied += 1
    for override in payload["omissions"]:
        key = override["key"]
        entry = by_key.get(key)
        if entry is None:
            raise IdentityError(f"{OVERRIDES_PATH}: unknown omission key {key!r}")
        entry.pop("resolution", None)
        entry.pop("reviewNote", None)
        outcome = {
            "disposition": override["disposition"],
            "reason": override["reviewNote"],
        }
        if "mediaType" in override:
            outcome["mediaType"] = override["mediaType"]
        entry["reviewOutcome"] = outcome
        omitted += 1
    return applied, omitted


def validate_overrides(identity_map: dict) -> None:
    payload = load_overrides()
    by_key = {entry["key"]: entry for entry in identity_map["works"]}
    all_keys: set[str] = set()
    work_keys = [entry.get("key") for entry in payload["works"]]
    omission_keys = [entry.get("key") for entry in payload["omissions"]]
    if work_keys != sorted(work_keys) or omission_keys != sorted(omission_keys):
        raise IdentityError(f"{OVERRIDES_PATH}: works and omissions must be sorted by key")
    for override in payload["works"]:
        if set(override) - {
            "key",
            "mediaType",
            "title",
            "releaseYear",
            "tmdbId",
            "imdbId",
            "reviewNote",
            "evidenceUrls",
        }:
            raise IdentityError(f"{OVERRIDES_PATH}: unsupported work override keys")
        key = override.get("key")
        if not isinstance(key, str) or key not in by_key or key in all_keys:
            raise IdentityError(f"{OVERRIDES_PATH}: invalid or duplicate work key {key!r}")
        all_keys.add(key)
        if override.get("mediaType") not in {"movie", "series"}:
            raise IdentityError(f"{OVERRIDES_PATH}: invalid media type for {key}")
        tmdb_id = override.get("tmdbId")
        if tmdb_id is not None and (not isinstance(tmdb_id, int) or tmdb_id <= 0):
            raise IdentityError(f"{OVERRIDES_PATH}: invalid TMDB ID for {key}")
        if "imdbId" in override and (
            not isinstance(override["imdbId"], str)
            or not IMDB_TITLE_RE.fullmatch(override["imdbId"])
        ):
            raise IdentityError(f"{OVERRIDES_PATH}: invalid IMDb ID for {key}")
        if not isinstance(override.get("reviewNote"), str) or not override["reviewNote"].strip():
            raise IdentityError(f"{OVERRIDES_PATH}: review note required for {key}")
        if tmdb_id is None:
            if "imdbId" not in override:
                raise IdentityError(f"{OVERRIDES_PATH}: IMDb-only override requires IMDb ID for {key}")
            if not isinstance(override.get("releaseYear"), int):
                raise IdentityError(f"{OVERRIDES_PATH}: IMDb-only override requires release year for {key}")
            evidence_urls = override.get("evidenceUrls")
            if not isinstance(evidence_urls, list) or not evidence_urls or not all(
                isinstance(value, str) and value.startswith("https://")
                for value in evidence_urls
            ):
                raise IdentityError(f"{OVERRIDES_PATH}: IMDb-only override requires evidence URLs for {key}")
        resolution = by_key[key].get("resolution")
        if not isinstance(resolution, dict) or resolution.get("mediaType") != override["mediaType"]:
            raise IdentityError(f"{OVERRIDES_PATH}: unapplied work override {key}")
        expected_method = (
            "reviewed-manual-override" if tmdb_id is not None else "reviewed-imdb-override"
        )
        if resolution.get("method") != expected_method:
            raise IdentityError(f"{OVERRIDES_PATH}: wrong resolution method for {key}")
        if tmdb_id is not None and resolution.get("tmdbId") != tmdb_id:
            raise IdentityError(f"{OVERRIDES_PATH}: stale TMDB resolution for {key}")
        if tmdb_id is None and (
            "tmdbId" in resolution
            or resolution.get("imdbId") != override["imdbId"]
            or resolution.get("releaseYear") != override["releaseYear"]
        ):
            raise IdentityError(f"{OVERRIDES_PATH}: stale IMDb-only resolution for {key}")
        if by_key[key].get("reviewNote") != override["reviewNote"]:
            raise IdentityError(f"{OVERRIDES_PATH}: stale review note for {key}")
    for override in payload["omissions"]:
        if set(override) - {
            "key",
            "mediaType",
            "disposition",
            "reviewNote",
            "evidenceUrls",
        }:
            raise IdentityError(f"{OVERRIDES_PATH}: invalid omission keys")
        key = override.get("key")
        if not isinstance(key, str) or key not in by_key or key in all_keys:
            raise IdentityError(f"{OVERRIDES_PATH}: invalid or duplicate omission key {key!r}")
        all_keys.add(key)
        if override.get("disposition") != "no-compatible-imdb-identity":
            raise IdentityError(f"{OVERRIDES_PATH}: invalid omission disposition for {key}")
        media_type = override.get("mediaType")
        if media_type is not None and media_type not in {"movie", "series"}:
            raise IdentityError(f"{OVERRIDES_PATH}: invalid omission media type for {key}")
        if by_key[key].get("mediaScope") == "mixed" and media_type is None:
            raise IdentityError(
                f"{OVERRIDES_PATH}: mixed-media omission requires media type for {key}"
            )
        if not isinstance(override.get("reviewNote"), str) or not override["reviewNote"].strip():
            raise IdentityError(f"{OVERRIDES_PATH}: review note required for {key}")
        evidence_urls = override.get("evidenceUrls")
        if not isinstance(evidence_urls, list) or not evidence_urls or not all(
            isinstance(value, str) and value.startswith("https://") for value in evidence_urls
        ):
            raise IdentityError(f"{OVERRIDES_PATH}: evidence URLs required for {key}")
        if "resolution" in by_key[key]:
            raise IdentityError(f"{OVERRIDES_PATH}: omitted work is also resolved: {key}")
        expected_outcome = {
            "disposition": override["disposition"],
            "reason": override["reviewNote"],
        }
        if media_type is not None:
            expected_outcome["mediaType"] = media_type
        if by_key[key].get("reviewOutcome") != expected_outcome:
            raise IdentityError(f"{OVERRIDES_PATH}: unapplied omission {key}")


def validate_resolution(entry: dict) -> bool:
    resolution = entry.get("resolution")
    if resolution is None:
        return False
    if not isinstance(resolution, dict):
        raise IdentityError(f"{entry.get('key')}: resolution must be an object")
    if resolution.get("mediaType") not in {"movie", "series"}:
        raise IdentityError(f"{entry.get('key')}: invalid resolved media type")
    if entry.get("mediaScope") == "movie" and resolution["mediaType"] != "movie":
        raise IdentityError(f"{entry.get('key')}: Film work resolved as non-movie")
    if not isinstance(resolution.get("title"), str) or not resolution["title"].strip():
        raise IdentityError(f"{entry.get('key')}: resolved work has no title")
    if not isinstance(resolution.get("releaseYear"), int):
        raise IdentityError(f"{entry.get('key')}: resolved work has no release year")
    tmdb_id = resolution.get("tmdbId")
    if tmdb_id is not None and (not isinstance(tmdb_id, int) or tmdb_id <= 0):
        raise IdentityError(f"{entry.get('key')}: resolved work has invalid TMDB ID")
    if not isinstance(resolution.get("imdbId"), str) or not IMDB_TITLE_RE.fullmatch(
        resolution["imdbId"]
    ):
        raise IdentityError(f"{entry.get('key')}: resolved work has no valid IMDb title ID")
    if not isinstance(resolution.get("method"), str) or not resolution["method"].strip():
        raise IdentityError(f"{entry.get('key')}: resolved work has no method")
    return True


def validate_candidates(entry: dict) -> bool:
    if "candidates" not in entry:
        return False
    candidates = entry["candidates"]
    if not isinstance(candidates, list) or len(candidates) > 8:
        raise IdentityError(f"{entry.get('key')}: candidates must be an array of at most 8 items")
    seen: set[tuple[str, int]] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise IdentityError(f"{entry.get('key')}: invalid candidate entry")
        media_type = candidate.get("mediaType")
        tmdb_id = candidate.get("tmdbId")
        if media_type not in {"movie", "series"}:
            raise IdentityError(f"{entry.get('key')}: candidate has invalid media type")
        if entry.get("mediaScope") == "movie" and media_type != "movie":
            raise IdentityError(f"{entry.get('key')}: Film candidate is not a movie")
        if not isinstance(tmdb_id, int) or tmdb_id <= 0:
            raise IdentityError(f"{entry.get('key')}: candidate has invalid TMDB ID")
        candidate_key = (media_type, tmdb_id)
        if candidate_key in seen:
            raise IdentityError(f"{entry.get('key')}: duplicate candidate {candidate_key}")
        seen.add(candidate_key)
        if not isinstance(candidate.get("title"), str) or not candidate["title"].strip():
            raise IdentityError(f"{entry.get('key')}: candidate has no title")
        if not isinstance(candidate.get("awardWindowPlausible"), bool):
            raise IdentityError(f"{entry.get('key')}: candidate has no award-window decision")
        for field in ("releaseYear", "lastAirYear"):
            if field in candidate and not isinstance(candidate[field], int):
                raise IdentityError(f"{entry.get('key')}: candidate has invalid {field}")
        if "imdbId" in candidate and (
            not isinstance(candidate["imdbId"], str)
            or not IMDB_TITLE_RE.fullmatch(candidate["imdbId"])
        ):
            raise IdentityError(f"{entry.get('key')}: candidate has invalid IMDb ID")
    plausible = [
        candidate
        for candidate in candidates
        if candidate["awardWindowPlausible"] and candidate.get("imdbId")
    ]
    if len(plausible) == 1:
        raise IdentityError(
            f"{entry.get('key')}: one unambiguous candidate remains but was not resolved"
        )
    return True


def validate_review_outcome(entry: dict) -> bool:
    outcome = entry.get("reviewOutcome")
    if outcome is None:
        return False
    if "resolution" in entry:
        raise IdentityError(f"{entry.get('key')}: work cannot be resolved and omitted")
    if not isinstance(outcome, dict) or set(outcome) not in (
        {"disposition", "reason"},
        {"disposition", "reason", "mediaType"},
    ):
        raise IdentityError(f"{entry.get('key')}: invalid review outcome")
    if outcome["disposition"] != "no-compatible-imdb-identity":
        raise IdentityError(f"{entry.get('key')}: invalid review disposition")
    if not isinstance(outcome["reason"], str) or not outcome["reason"].strip():
        raise IdentityError(f"{entry.get('key')}: review outcome requires a reason")
    if "mediaType" in outcome and outcome["mediaType"] not in {"movie", "series"}:
        raise IdentityError(f"{entry.get('key')}: review outcome has invalid media type")
    if entry.get("mediaScope") == "mixed" and "mediaType" not in outcome:
        raise IdentityError(f"{entry.get('key')}: mixed-media review outcome needs media type")
    return True


def validate_map(
    identity_map: dict, complete: bool, attempted: bool, programme: str | None
) -> tuple[int, int, int, int]:
    works = identity_map.get("works")
    recipients = identity_map.get("recipients")
    if not isinstance(works, list) or not isinstance(recipients, list):
        raise IdentityError("BAFTA identity map has invalid work or recipient arrays")
    resolved_works = 0
    attempted_works = 0
    reviewed_outcomes = 0
    tmdb_relationships: dict[tuple[str, int], str] = {}
    imdb_relationships: dict[str, tuple[str, int]] = {}
    for entry in works:
        if validate_resolution(entry):
            resolved_works += 1
            attempted_works += 1
            resolution = entry["resolution"]
            tmdb_id = resolution.get("tmdbId")
            tmdb_key = (
                (resolution["mediaType"], tmdb_id) if tmdb_id is not None else None
            )
            if tmdb_key is not None:
                previous_imdb = tmdb_relationships.get(tmdb_key)
                if previous_imdb is not None and previous_imdb != resolution["imdbId"]:
                    raise IdentityError(f"{entry.get('key')}: TMDB identity maps to conflicting IMDb IDs")
                tmdb_relationships[tmdb_key] = resolution["imdbId"]
            previous_tmdb = imdb_relationships.get(resolution["imdbId"])
            if previous_tmdb is not None and tmdb_key is not None and previous_tmdb != tmdb_key:
                raise IdentityError(f"{entry.get('key')}: IMDb identity maps to conflicting TMDB IDs")
            if tmdb_key is not None:
                imdb_relationships[resolution["imdbId"]] = tmdb_key
        elif validate_review_outcome(entry):
            reviewed_outcomes += 1
            attempted_works += 1
        elif validate_candidates(entry):
            attempted_works += 1
    resolved_recipients = sum(
        isinstance(entry.get("resolution"), dict) for entry in recipients
    )
    scoped_works = [
        entry
        for entry in works
        if programme is None or identity_in_current_programme(entry, programme)
    ]
    scoped_complete = sum(
        "resolution" in entry or "reviewOutcome" in entry for entry in scoped_works
    )
    scoped_attempted = sum(
        "resolution" in entry or "reviewOutcome" in entry or "candidates" in entry
        for entry in scoped_works
    )
    scope_label = programme or "BAFTA"
    if complete and scoped_complete != len(scoped_works):
        raise IdentityError(
            f"{len(scoped_works) - scoped_complete} {scope_label} work identities remain unreviewed"
        )
    if attempted and scoped_attempted != len(scoped_works):
        raise IdentityError(
            f"{len(scoped_works) - scoped_attempted} {scope_label} work identities have not been attempted"
        )
    return len(works), resolved_works, len(recipients), resolved_recipients


def write_map(identity_map: dict) -> None:
    IDENTITY_MAP_PATH.write_text(
        json.dumps(identity_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmdb", action="store_true")
    parser.add_argument("--reuse-canonical", action="store_true")
    parser.add_argument("--apply-overrides", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("--attempted", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retry-candidates", action="store_true")
    parser.add_argument(
        "--programme", choices=("film", "television", "television-craft")
    )
    args = parser.parse_args()
    if not (args.tmdb or args.reuse_canonical or args.apply_overrides or args.check):
        parser.error("choose --tmdb, --reuse-canonical, --apply-overrides, or --check")
    if args.workers < 1 or args.offset < 0 or (args.limit is not None and args.limit < 1):
        parser.error("workers and limit must be positive; offset cannot be negative")
    try:
        identity_map = load_json(IDENTITY_MAP_PATH)
        reused = 0
        applied = 0
        omitted = 0
        if args.reuse_canonical:
            reused = reuse_canonical_works(identity_map)
        if args.tmdb:
            enrich_works(
                identity_map,
                args.workers,
                args.offset,
                args.limit,
                args.retry_candidates,
                args.programme,
            )
        if args.apply_overrides:
            applied, omitted = apply_overrides(identity_map)
        work_count, resolved_works, recipient_count, resolved_recipients = validate_map(
            identity_map, args.complete, args.attempted, args.programme
        )
        if args.apply_overrides or args.check:
            validate_overrides(identity_map)
        if args.tmdb or args.reuse_canonical or args.apply_overrides:
            write_map(identity_map)
        print(
            "BAFTA identity map: "
            f"{resolved_works}/{work_count} works resolved; "
            f"{resolved_recipients}/{recipient_count} credited recipients resolved"
            f"; {reused} existing canonical identities reused; "
            f"{applied} manual overrides and {omitted} reviewed omissions applied."
        )
        return 0
    except (IdentityError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
