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

from bafta_common import SOURCE_DIR, load_json
from enrich_golden_globes_identities import (
    IdentityError,
    candidate_titles,
    clean_text,
    normalized_title,
    title_variants,
    tmdb_json,
)


IDENTITY_MAP_PATH = SOURCE_DIR / "identity-map.json"
TOKEN_ENV = "TMDB_API_READ_TOKEN"
IMDB_TITLE_RE = re.compile(r"tt\d+")


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
) -> None:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise IdentityError(f"{TOKEN_ENV} is required for --tmdb")
    pending = [
        entry
        for entry in identity_map["works"]
        if "resolution" not in entry and (retry_candidates or "candidates" not in entry)
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
    if not isinstance(resolution.get("tmdbId"), int) or resolution["tmdbId"] <= 0:
        raise IdentityError(f"{entry.get('key')}: resolved work has no valid TMDB ID")
    if not isinstance(resolution.get("imdbId"), str) or not IMDB_TITLE_RE.fullmatch(
        resolution["imdbId"]
    ):
        raise IdentityError(f"{entry.get('key')}: resolved work has no valid IMDb title ID")
    if not isinstance(resolution.get("method"), str) or not resolution["method"].strip():
        raise IdentityError(f"{entry.get('key')}: resolved work has no method")
    return True


def validate_map(identity_map: dict, complete: bool) -> tuple[int, int, int, int]:
    works = identity_map.get("works")
    recipients = identity_map.get("recipients")
    if not isinstance(works, list) or not isinstance(recipients, list):
        raise IdentityError("BAFTA identity map has invalid work or recipient arrays")
    resolved_works = sum(validate_resolution(entry) for entry in works)
    resolved_recipients = sum(
        isinstance(entry.get("resolution"), dict) for entry in recipients
    )
    if complete and resolved_works != len(works):
        raise IdentityError(f"{len(works) - resolved_works} work identities remain unresolved")
    return len(works), resolved_works, len(recipients), resolved_recipients


def write_map(identity_map: dict) -> None:
    IDENTITY_MAP_PATH.write_text(
        json.dumps(identity_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmdb", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retry-candidates", action="store_true")
    args = parser.parse_args()
    if not (args.tmdb or args.check):
        parser.error("choose --tmdb or --check")
    if args.workers < 1 or args.offset < 0 or (args.limit is not None and args.limit < 1):
        parser.error("workers and limit must be positive; offset cannot be negative")
    try:
        identity_map = load_json(IDENTITY_MAP_PATH)
        if args.tmdb:
            enrich_works(
                identity_map,
                args.workers,
                args.offset,
                args.limit,
                args.retry_candidates,
            )
        work_count, resolved_works, recipient_count, resolved_recipients = validate_map(
            identity_map, args.complete
        )
        if args.tmdb:
            write_map(identity_map)
        print(
            "BAFTA identity map: "
            f"{resolved_works}/{work_count} works resolved; "
            f"{resolved_recipients}/{recipient_count} credited recipients resolved."
        )
        return 0
    except (IdentityError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
