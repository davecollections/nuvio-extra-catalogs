"""Shared canonical BAFTA programme generation."""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from bafta_common import (
    SNAPSHOTS,
    current_programme_for_category,
    load_category_contract,
    load_json,
    selected_winners,
    work_key,
)
from build_bafta_identity_seed import IDENTITY_MAP_PATH, input_digest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_REFERENCE = "../../../../schema/award-results.schema.json"
SOURCE_NAME = "British Academy of Film and Television Arts"


class CanonicalError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanonicalConfig:
    programme: str
    snapshot_programme: str
    award_body_id: str
    award_name: str
    source_reference: str
    expected_results: int
    expected_work_links: int
    expected_source_duplicates: int = 0

    @property
    def body_dir(self) -> Path:
        return ROOT / "data" / "awards" / self.award_body_id

    @property
    def results_dir(self) -> Path:
        return self.body_dir / "results"

    @property
    def award_path(self) -> Path:
        return self.body_dir / "award.json"

    @property
    def categories_path(self) -> Path:
        return self.body_dir / "categories.json"


FILM_CONFIG = CanonicalConfig(
    programme="film",
    snapshot_programme="film",
    award_body_id="bafta-film",
    award_name="BAFTA Film Awards",
    source_reference="https://www.bafta.org/awards/film/",
    expected_results=1302,
    expected_work_links=1321,
)

TELEVISION_CONFIG = CanonicalConfig(
    programme="television",
    snapshot_programme="television",
    award_body_id="bafta-television",
    award_name="BAFTA Television Awards",
    source_reference="https://www.bafta.org/awards/television/",
    expected_results=931,
    expected_work_links=970,
    expected_source_duplicates=7,
)


def serialized(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def compact_serialized(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"


def category_registry(config: CanonicalConfig) -> dict:
    definitions, source_mapping, _, _, _ = load_category_contract()
    programme = next(
        entry for entry in definitions["programmes"] if entry["id"] == config.programme
    )
    aliases: dict[str, list[str]] = {
        category["id"]: [] for category in programme["categories"]
    }
    for (_, label), category in source_mapping.items():
        if current_programme_for_category(category["id"]) != config.programme:
            continue
        if label == category["name"] or label in aliases[category["id"]]:
            continue
        aliases[category["id"]].append(label)

    categories = []
    for definition in programme["categories"]:
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
        "awardBodyId": config.award_body_id,
        "categories": categories,
    }


def award_registry(config: CanonicalConfig, result_years: list[int]) -> dict:
    ceremony_numbers = [year - 1947 for year in result_years]
    return {
        "schemaVersion": 1,
        "id": config.award_body_id,
        "name": config.award_name,
        "organization": SOURCE_NAME,
        "authoritativeSources": [
            {"name": SOURCE_NAME, "reference": config.source_reference}
        ],
        "ceremonyCoverage": {
            "firstCeremonyNumber": min(ceremony_numbers),
            "lastCeremonyNumber": max(ceremony_numbers),
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
    media_type = outcome.get("mediaType", selected["category"]["mediaType"])
    if media_type not in {"movie", "series"}:
        raise CanonicalError(f"reviewed outcome {key!r} has no concrete media type")
    return (
        {"mediaType": media_type, "title": selected["workTitle"]},
        outcome["reason"],
    )


def append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def grouped_winners(config: CanonicalConfig) -> list[dict]:
    grouped: OrderedDict[tuple[int, str], dict] = OrderedDict()
    for selected in selected_winners():
        if current_programme_for_category(selected["category"]["id"]) != config.programme:
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
        result["people"] = [{"name": name} for name in group["recipientValues"]]
    if notes:
        result["note"] = " ".join(notes)
    return result


def build_files(config: CanonicalConfig) -> dict[Path, str]:
    identity_map = load_json(IDENTITY_MAP_PATH)
    if identity_map.get("inputSha256") != input_digest():
        raise CanonicalError("reviewed identity map does not match the BAFTA sources")
    identities = {entry["key"]: entry for entry in identity_map.get("works", [])}
    snapshot = load_json(SNAPSHOTS[config.snapshot_programme])
    result_years = [entry["year"] for entry in snapshot["resultsPages"]]
    if len(result_years) != len(set(result_years)):
        raise CanonicalError("snapshot contains duplicate result years")
    source = {
        "name": SOURCE_NAME,
        "reference": config.source_reference,
        "checkedAt": snapshot["checkedAt"],
    }

    by_year: OrderedDict[int, list[dict]] = OrderedDict(
        (year, []) for year in result_years
    )
    relationships_by_year: dict[int, set[str]] = {
        year: set() for year in result_years
    }
    work_links = 0
    source_duplicates = 0
    for group in grouped_winners(config):
        if group["year"] not in by_year:
            raise CanonicalError(f"winner year {group['year']} has no result page")
        result = canonical_result(group, identities)
        relationship = {
            field: result[field]
            for field in (
                "categoryId",
                "status",
                "sourceCategory",
                "work",
                "works",
                "people",
                "recipientLabel",
            )
            if field in result
        }
        fingerprint = json.dumps(
            relationship, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        if fingerprint in relationships_by_year[group["year"]]:
            source_duplicates += 1
            continue
        relationships_by_year[group["year"]].add(fingerprint)
        by_year[group["year"]].append(result)
        work_links += len(result.get("works", [result.get("work")]))

    result_count = sum(map(len, by_year.values()))
    if result_count != config.expected_results or work_links != config.expected_work_links:
        raise CanonicalError(
            f"unexpected {config.award_name} totals: {result_count} results, "
            f"{work_links} work links"
        )
    if source_duplicates != config.expected_source_duplicates:
        raise CanonicalError(
            f"unexpected {config.award_name} duplicate-source total: "
            f"{source_duplicates}"
        )

    files = {
        config.award_path: serialized(award_registry(config, result_years)),
        config.categories_path: serialized(category_registry(config)),
    }
    for year, results in by_year.items():
        ceremony_number = year - 1947
        payload = {
            "$schema": SCHEMA_REFERENCE,
            "schemaVersion": 1,
            "awardBodyId": config.award_body_id,
            "ceremony": {"year": year, "number": ceremony_number},
            "source": source,
            "results": results,
        }
        files[config.results_dir / f"{ceremony_number:03d}-{year}.json"] = (
            compact_serialized(payload)
        )
    return files


def write_files(config: CanonicalConfig, files: dict[Path, str]) -> None:
    config.results_dir.mkdir(parents=True, exist_ok=True)
    expected_results = {path for path in files if path.parent == config.results_dir}
    for path in config.results_dir.glob("*.json"):
        if path not in expected_results:
            path.unlink()
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_files(config: CanonicalConfig, files: dict[Path, str]) -> None:
    actual_results = (
        set(config.results_dir.glob("*.json")) if config.results_dir.is_dir() else set()
    )
    expected_results = {path for path in files if path.parent == config.results_dir}
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


def main(config: CanonicalConfig) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        parser.error("choose --write or --check")
    try:
        files = build_files(config)
        if args.write:
            write_files(config, files)
        if args.check:
            check_files(config, files)
        result_count = 0
        work_links = 0
        for path, content in files.items():
            if path.parent != config.results_dir:
                continue
            payload = json.loads(content)
            result_count += len(payload["results"])
            work_links += sum(
                len(result.get("works", [result.get("work")]))
                for result in payload["results"]
            )
        print(
            f"{config.award_name} canonical data: "
            f"{len(files) - 2} ceremonies, {result_count} results, "
            f"{work_links} work links."
        )
        return 0
    except (CanonicalError, KeyError, OSError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
