#!/usr/bin/env python3
"""Build canonical Golden Globes ceremony files from the reviewed snapshot.

The committed Golden Globes snapshot is the award authority. The committed
identity map supplies reviewed TMDB/IMDb relationships without any live lookup
during generation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from enrich_golden_globes_identities import (
    CATEGORIES_PATH,
    IDENTITY_MAP_PATH,
    SNAPSHOT_PATH,
    clean_text,
    entity_key,
    load_json,
    select_work_item,
    snapshot_digest,
    source_labels,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "data" / "awards" / "golden-globes" / "results"
SCHEMA_REFERENCE = "../../../../schema/award-results.schema.json"


class CanonicalError(RuntimeError):
    pass


def indexed(entries: list[dict], label: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for entry in entries:
        key = entry.get("key")
        if not isinstance(key, str) or not key:
            raise CanonicalError(f"identity map has an invalid {label} key")
        if key in result:
            raise CanonicalError(f"identity map has duplicate {label} key {key!r}")
        result[key] = entry
    return result


def canonical_work(
    item: dict,
    *,
    category: dict,
    ceremony_year: int,
    works_by_key: dict[str, dict],
) -> dict:
    key = entity_key(
        item,
        kind="work",
        year=ceremony_year,
        category_media_type=category["mediaType"],
    )
    entry = works_by_key.get(key)
    if entry is None:
        raise CanonicalError(f"no reviewed work identity for {key!r}")
    resolution = entry.get("resolution")
    if not isinstance(resolution, dict):
        raise CanonicalError(f"work identity {key!r} is unresolved")
    work = {
        "mediaType": resolution["mediaType"],
        "title": clean_text(resolution["title"]),
    }
    for field in ("releaseYear", "tmdbId", "imdbId"):
        if field in resolution:
            work[field] = resolution[field]
    return work


def canonical_person(
    item: dict,
    *,
    category: dict,
    ceremony_year: int,
    people_by_key: dict[str, dict],
) -> dict:
    key = entity_key(
        item,
        kind="person",
        year=ceremony_year,
        category_media_type=category["mediaType"],
    )
    entry = people_by_key.get(key)
    if entry is None:
        raise CanonicalError(f"no reviewed person identity for {key!r}")
    resolution = entry.get("resolution", {})
    name = resolution.get("name") or clean_text(item["title"])
    person = {"name": clean_text(name)}
    for field in ("tmdbId", "imdbId"):
        if field in resolution:
            person[field] = resolution[field]
    return person


def canonical_result(
    winner: dict,
    *,
    source_category: str,
    category: dict,
    ceremony_year: int,
    works_by_key: dict[str, dict],
    people_by_key: dict[str, dict],
) -> dict:
    result = {
        "categoryId": category["id"],
        "status": "winner",
        "sourceCategory": source_category,
        "sourceRecordId": winner["officialId"],
    }
    work_item = select_work_item(category, winner)
    if work_item is not None:
        result["work"] = canonical_work(
            work_item,
            category=category,
            ceremony_year=ceremony_year,
            works_by_key=works_by_key,
        )

    recipients = winner.get("recipients", [])
    if winner.get("nomineeType") == "people":
        result["people"] = [
            canonical_person(
                person,
                category=category,
                ceremony_year=ceremony_year,
                people_by_key=people_by_key,
            )
            for person in recipients
        ]
    elif category["id"] == "original-song-motion-picture" and recipients:
        result["recipientLabel"] = " / ".join(
            clean_text(recipient["title"]) for recipient in recipients
        )

    countries = []
    for recipient in recipients:
        for country in recipient.get("countries", []):
            country = clean_text(country)
            if country and country not in countries:
                countries.append(country)
    if countries:
        result["recipientLabel"] = " / ".join(countries)

    if category["id"] == "original-song-motion-picture" and not recipients:
        result["note"] = "The official archive does not provide the winning song title."
    return result


def build_files() -> dict[Path, str]:
    snapshot = load_json(SNAPSHOT_PATH)
    categories = load_json(CATEGORIES_PATH)
    identity_map = load_json(IDENTITY_MAP_PATH)
    if identity_map.get("snapshotSha256") != snapshot_digest(snapshot):
        raise CanonicalError("reviewed identity map does not match the official snapshot")
    labels = source_labels(categories)
    works_by_key = indexed(identity_map.get("works", []), "work")
    people_by_key = indexed(identity_map.get("people", []), "person")
    source = snapshot.get("source", {})
    source_record = {
        "name": source.get("name"),
        "reference": source.get("reference"),
        "checkedAt": source.get("checkedAt"),
    }
    if not all(isinstance(value, str) and value for value in source_record.values()):
        raise CanonicalError("snapshot source metadata is incomplete")

    files: dict[Path, str] = {}
    matched = 0
    for year_entry in snapshot.get("years", []):
        year = year_entry["year"]
        number = year_entry["ceremonyNumber"]
        results = []
        for group in year_entry.get("groups", []):
            source_category = group.get("officialCategory")
            category = labels.get(source_category)
            if category is None:
                continue
            for winner in group.get("winners", []):
                results.append(
                    canonical_result(
                        winner,
                        source_category=source_category,
                        category=category,
                        ceremony_year=year,
                        works_by_key=works_by_key,
                        people_by_key=people_by_key,
                    )
                )
                matched += 1
        payload = {
            "$schema": SCHEMA_REFERENCE,
            "schemaVersion": 1,
            "awardBodyId": "golden-globes",
            "ceremony": {"year": year, "number": number},
            "source": source_record,
            "results": results,
        }
        path = RESULTS_DIR / f"{number:03d}-{year}.json"
        files[path] = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"

    expected = identity_map.get("matchedCurrentCategoryWinnerRecords")
    if matched != expected:
        raise CanonicalError(
            f"built {matched} results, but the reviewed identity map records {expected}"
        )
    return files


def write_files(files: dict[Path, str]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    expected_paths = set(files)
    for existing in RESULTS_DIR.glob("*.json"):
        if existing not in expected_paths:
            existing.unlink()
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def check_files(files: dict[Path, str]) -> None:
    actual_paths = set(RESULTS_DIR.glob("*.json")) if RESULTS_DIR.is_dir() else set()
    expected_paths = set(files)
    if actual_paths != expected_paths:
        missing = sorted(path.name for path in expected_paths - actual_paths)
        extra = sorted(path.name for path in actual_paths - expected_paths)
        raise CanonicalError(f"canonical file set differs; missing={missing}, extra={extra}")
    changed = [path.name for path, content in files.items() if path.read_text(encoding="utf-8") != content]
    if changed:
        raise CanonicalError(f"canonical files are stale: {changed}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        parser.error("choose --write or --check")
    try:
        files = build_files()
        if args.write:
            write_files(files)
        if args.check:
            check_files(files)
        result_count = sum(json.loads(content)["results"].__len__() for content in files.values())
        print(f"Golden Globes canonical data: {len(files)} ceremonies, {result_count} results.")
        return 0
    except (CanonicalError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
