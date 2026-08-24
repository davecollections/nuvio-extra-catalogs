#!/usr/bin/env python3
"""Build canonical BAFTA Film data from the reviewed first-party snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

from bafta_common import (
    DEFINITIONS_PATH,
    SNAPSHOTS,
    load_category_contract,
    load_json,
    selected_winners,
    work_key,
)
from build_bafta_identity_seed import IDENTITY_MAP_PATH, input_digest


ROOT = Path(__file__).resolve().parents[1]
BODY_DIR = ROOT / "data" / "awards" / "bafta-film"
RESULTS_DIR = BODY_DIR / "results"
AWARD_PATH = BODY_DIR / "award.json"
CATEGORIES_PATH = BODY_DIR / "categories.json"
SCHEMA_REFERENCE = "../../../../schema/award-results.schema.json"
AWARD_BODY_ID = "bafta-film"
SOURCE_NAME = "British Academy of Film and Television Arts"
SOURCE_REFERENCE = "https://www.bafta.org/awards/film/"


class CanonicalError(RuntimeError):
    pass


def serialized(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def compact_serialized(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"


def category_registry() -> dict:
    definitions, source_mapping, _, _, _ = load_category_contract()
    film = next(
        programme for programme in definitions["programmes"] if programme["id"] == "film"
    )
    aliases: dict[str, list[str]] = {
        category["id"]: [] for category in film["categories"]
    }
    for (programme, label), category in source_mapping.items():
        if programme != "film" or label == category["name"]:
            continue
        if label not in aliases[category["id"]]:
            aliases[category["id"]].append(label)

    categories = []
    for definition in film["categories"]:
        category = {
            "id": definition["id"],
            "name": definition["name"],
            "aliases": sorted(aliases[definition["id"]], key=str.casefold),
            "mediaType": definition["mediaType"],
            "recipientKind": definition["recipientKind"],
        }
        if "creditRole" in definition:
            category["creditRole"] = definition["creditRole"]
        categories.append(category)
    return {
        "schemaVersion": 1,
        "awardBodyId": AWARD_BODY_ID,
        "categories": categories,
    }


def award_registry() -> dict:
    return {
        "schemaVersion": 1,
        "id": AWARD_BODY_ID,
        "name": "BAFTA Film Awards",
        "organization": SOURCE_NAME,
        "authoritativeSources": [
            {"name": SOURCE_NAME, "reference": SOURCE_REFERENCE}
        ],
        "ceremonyCoverage": {
            "firstCeremonyNumber": 2,
            "lastCeremonyNumber": 79,
        },
    }


def canonical_work(selected: dict, identities: dict[str, dict]) -> tuple[dict, str | None]:
    key = work_key(selected)
    identity = identities.get(key)
    if identity is None:
        raise CanonicalError(f"no reviewed work identity for {key!r}")
    resolution = identity.get("resolution")
    if isinstance(resolution, dict):
        work = {
            "mediaType": resolution["mediaType"],
            "title": resolution["title"],
        }
        for field in ("releaseYear", "tmdbId", "imdbId"):
            if field in resolution:
                work[field] = resolution[field]
        return work, None

    outcome = identity.get("reviewOutcome")
    if not isinstance(outcome, dict):
        raise CanonicalError(f"work identity {key!r} is unresolved")
    media_type = selected["category"]["mediaType"]
    if media_type == "mixed":
        raise CanonicalError(f"reviewed outcome {key!r} has no concrete media type")
    return (
        {"mediaType": media_type, "title": selected["workTitle"]},
        outcome["reason"],
    )


def append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def grouped_film_winners() -> list[dict]:
    grouped: OrderedDict[tuple[int, str], dict] = OrderedDict()
    for selected in selected_winners():
        if selected["programme"] != "film":
            continue
        key = (selected["year"], selected["nominationId"])
        current = grouped.get(key)
        if current is None:
            current = {
                "year": selected["year"],
                "nominationId": selected["nominationId"],
                "category": selected["category"],
                "sourceCategory": selected["sourceCategory"],
                "recipientValues": [],
                "works": [],
            }
            grouped[key] = current
        elif (
            current["category"]["id"] != selected["category"]["id"]
            or current["sourceCategory"] != selected["sourceCategory"]
        ):
            raise CanonicalError(f"inconsistent split winner {key!r}")
        for recipient in selected["recipientValues"]:
            append_unique(current["recipientValues"], recipient)
        current["works"].append(selected)
    return list(grouped.values())


def canonical_result(group: dict, identities: dict[str, dict]) -> dict:
    result = {
        "categoryId": group["category"]["id"],
        "status": "winner",
        "sourceCategory": group["sourceCategory"],
        "sourceRecordId": int(group["nominationId"]),
    }
    works = []
    notes = []
    for selected in group["works"]:
        work, note = canonical_work(selected, identities)
        works.append(work)
        if note and note not in notes:
            notes.append(note)
    if len(works) == 1:
        result["work"] = works[0]
    else:
        result["works"] = works
    if group["recipientValues"]:
        result["people"] = [
            {"name": name} for name in group["recipientValues"]
        ]
    if notes:
        result["note"] = " ".join(notes)
    return result


def build_files() -> dict[Path, str]:
    identity_map = load_json(IDENTITY_MAP_PATH)
    if identity_map.get("inputSha256") != input_digest():
        raise CanonicalError("reviewed identity map does not match the BAFTA sources")
    identities = {
        entry["key"]: entry for entry in identity_map.get("works", [])
    }
    snapshot = load_json(SNAPSHOTS["film"])
    checked_at = snapshot["checkedAt"]
    source = {
        "name": SOURCE_NAME,
        "reference": SOURCE_REFERENCE,
        "checkedAt": checked_at,
    }

    by_year: OrderedDict[int, list[dict]] = OrderedDict()
    work_links = 0
    for group in grouped_film_winners():
        result = canonical_result(group, identities)
        by_year.setdefault(group["year"], []).append(result)
        work_links += len(result.get("works", [result.get("work")]))

    result_pages = {entry["year"] for entry in snapshot["resultsPages"]}
    if set(by_year) != result_pages:
        raise CanonicalError("canonical years do not match the Film result pages")
    if sum(map(len, by_year.values())) != 1302 or work_links != 1321:
        raise CanonicalError(
            f"unexpected Film totals: {sum(map(len, by_year.values()))} results, "
            f"{work_links} work links"
        )

    files = {
        AWARD_PATH: serialized(award_registry()),
        CATEGORIES_PATH: serialized(category_registry()),
    }
    for year, results in by_year.items():
        ceremony_number = year - 1947
        payload = {
            "$schema": SCHEMA_REFERENCE,
            "schemaVersion": 1,
            "awardBodyId": AWARD_BODY_ID,
            "ceremony": {"year": year, "number": ceremony_number},
            "source": source,
            "results": results,
        }
        files[RESULTS_DIR / f"{ceremony_number:03d}-{year}.json"] = compact_serialized(
            payload
        )
    return files


def write_files(files: dict[Path, str]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    expected_results = {path for path in files if path.parent == RESULTS_DIR}
    for path in RESULTS_DIR.glob("*.json"):
        if path not in expected_results:
            path.unlink()
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_files(files: dict[Path, str]) -> None:
    actual_results = set(RESULTS_DIR.glob("*.json")) if RESULTS_DIR.is_dir() else set()
    expected_results = {path for path in files if path.parent == RESULTS_DIR}
    if actual_results != expected_results:
        missing = sorted(path.name for path in expected_results - actual_results)
        extra = sorted(path.name for path in actual_results - expected_results)
        raise CanonicalError(
            f"canonical result set differs; missing={missing}, extra={extra}"
        )
    changed = [
        str(path.relative_to(ROOT))
        for path, content in files.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]
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
        result_count = 0
        work_links = 0
        for path, content in files.items():
            if path.parent != RESULTS_DIR:
                continue
            payload = json.loads(content)
            result_count += len(payload["results"])
            work_links += sum(
                len(result.get("works", [result.get("work")]))
                for result in payload["results"]
            )
        print(
            "BAFTA Film canonical data: "
            f"{len(files) - 2} ceremonies, {result_count} results, "
            f"{work_links} work links."
        )
        return 0
    except (CanonicalError, KeyError, OSError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
