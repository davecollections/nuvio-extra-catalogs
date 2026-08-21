#!/usr/bin/env python3
"""Find mixed-category series identities with plausible TMDB movie matches.

Golden Globes television categories combine series, limited series, and made-for-
television movies. The official archive uses a single ``tv-show`` URL namespace,
so this live maintenance audit surfaces exact-title movie candidates for human
review rather than assuming that URL namespace is a media classification.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from enrich_golden_globes_identities import (
    IDENTITY_MAP_PATH,
    IdentityError,
    TOKEN_ENV,
    candidate_year,
    load_json,
    normalized_title,
    title_variants,
    tmdb_json,
)


class AuditError(RuntimeError):
    pass


def exact_movie_candidates(entry: dict, token: str) -> tuple[str, list[dict]]:
    normalized = {
        normalized_title(variant)
        for title in [*entry["titles"], entry["resolution"]["title"]]
        for variant in title_variants(title)
    }
    expected_years = [year - 1 for year in entry["ceremonyYears"]]
    candidates: dict[int, dict] = {}
    for title in entry["titles"]:
        for query in title_variants(title):
            payload = tmdb_json(
                "/search/movie",
                token,
                {"query": query, "include_adult": "false", "language": "en-US", "page": 1},
            )
            for candidate in payload.get("results", []):
                candidate_titles = [candidate.get("title"), candidate.get("original_title")]
                if not any(
                    isinstance(value, str) and normalized_title(value) in normalized
                    for value in candidate_titles
                ):
                    continue
                year = candidate_year(candidate)
                distance = min(
                    (abs(year - expected) for expected in expected_years), default=999
                ) if year else 999
                if distance <= 2:
                    candidates[candidate["id"]] = {
                        "tmdbId": candidate["id"],
                        "title": candidate.get("title"),
                        "releaseYear": year,
                        "awardYearDistance": distance,
                    }
    return entry["key"], sorted(
        candidates.values(), key=lambda value: (value["awardYearDistance"], value["tmdbId"])
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    token = os.environ.get(TOKEN_ENV)
    if not token:
        print(f"ERROR: {TOKEN_ENV} is required", file=sys.stderr)
        return 1
    try:
        identity_map = load_json(IDENTITY_MAP_PATH)
        entries = [
            entry
            for entry in identity_map.get("works", [])
            if "mixed" in entry.get("categoryMediaTypes", [])
            and entry.get("resolution", {}).get("mediaType") == "series"
        ]
        findings = []
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(exact_movie_candidates, entry, token): entry for entry in entries
            }
            for future in as_completed(futures):
                key, candidates = future.result()
                if not candidates:
                    continue
                entry = next(value for value in entries if value["key"] == key)
                findings.append(
                    {
                        "key": key,
                        "officialTitles": entry["titles"],
                        "ceremonyYears": entry["ceremonyYears"],
                        "categoryIds": entry["categoryIds"],
                        "currentResolution": entry["resolution"],
                        "movieCandidates": candidates,
                    }
                )
        findings.sort(key=lambda value: value["key"])
        print(json.dumps(findings, ensure_ascii=True, indent=2))
        print(
            f"Mixed-media audit: {len(findings)} of {len(entries)} series identities "
            "have an exact-title, award-year movie candidate.",
            file=sys.stderr,
        )
        return 0
    except (AuditError, IdentityError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
