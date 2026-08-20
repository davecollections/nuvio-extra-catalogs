#!/usr/bin/env python3
"""Validate Awards people against the canonical Nuvio People artwork manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPO_ROOT / "reports" / "issue-17-awards-people-artwork-integration.json"

PEOPLE_ASSETS_REPOSITORY = "https://github.com/davecollections/nuvio-people-assets"
PEOPLE_ASSETS_COMMIT = "4277be3dcfe3b6806568438ca5408d89ce29f4b2"
PINNED_MANIFEST_URL = (
    "https://raw.githubusercontent.com/davecollections/nuvio-people-assets/"
    f"{PEOPLE_ASSETS_COMMIT}/manifests/people.json"
)
RUNTIME_MANIFEST_URL = (
    "https://raw.githubusercontent.com/davecollections/nuvio-people-assets/"
    "main/manifests/people.json"
)
PEOPLE_MANIFEST_SHA256 = "8ea20357324089f7c6c3004cb9f4c8c191358c36de99a8dc0386ede3efadbf94"

BUILDER_REPOSITORY = "https://github.com/davecollections/tmdb-id-lookup"
BUILDER_MIGRATION_COMMIT = "e9eb3b24a93b7e6bbca295a340d035cb018293d9"
BUILDER_VERIFIED_BASELINE_COMMIT = "fa79389eda7d5ed59707420a16839055e7555b8c"

PEOPLE_MANIFEST_SCHEMA_VERSION = 2
CORE_ASSET_KEYS = ("poster", "landscape", "titleLogo", "hero")
FOCUS_ASSET_KEYS = ("focusPoster", "focusLandscape")
ALL_ASSET_KEYS = CORE_ASSET_KEYS + FOCUS_ASSET_KEYS
MEMBERSHIPS = {"actor", "director"}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
MAX_SAFE_INTEGER = 2**53 - 1
ASSET_ORIGIN = "raw.githubusercontent.com"
ASSET_PATH_PREFIX = "/davecollections/nuvio-people-assets/main/assets/people/"

CATEGORIES = (
    {
        "categoryId": "best-actor",
        "sourceType": "PERSON",
        "requiredMembership": "actor",
        "peoplePath": REPO_ROOT
        / "data"
        / "generated"
        / "academy-best-actor-winners.people.json",
    },
    {
        "categoryId": "best-actress",
        "sourceType": "PERSON",
        "requiredMembership": "actor",
        "peoplePath": REPO_ROOT
        / "data"
        / "generated"
        / "academy-best-actress-winners.people.json",
    },
    {
        "categoryId": "best-director",
        "sourceType": "DIRECTOR",
        "requiredMembership": "director",
        "peoplePath": REPO_ROOT
        / "data"
        / "generated"
        / "academy-best-director-winners.people.json",
    },
)

SAMPLES = (
    {"categoryId": "best-actor", "tmdbPersonId": 17838},
    {"categoryId": "best-actress", "tmdbPersonId": 1640439},
    {"categoryId": "best-director", "tmdbPersonId": 1269},
)


class IntegrationError(RuntimeError):
    pass


def is_positive_safe_integer(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 < value <= MAX_SAFE_INTEGER
    )


def load_json_file(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise IntegrationError(f"{path}: expected a JSON object")
    return value


def load_manifest_bytes(source: str) -> bytes:
    if re.match(r"^[A-Za-z]:[\\/]", source):
        try:
            return Path(source).read_bytes()
        except OSError as exc:
            raise IntegrationError(f"could not read People manifest {source}: {exc}") from exc

    parts = urlsplit(source)
    if parts.scheme:
        if parts.scheme != "https" or not parts.netloc:
            raise IntegrationError("People manifest source must be a local path or an HTTPS URL")
        request = urllib.request.Request(source, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except (OSError, urllib.error.URLError) as exc:
            raise IntegrationError(f"could not fetch People manifest {source}: {exc}") from exc

    path = Path(source)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise IntegrationError(f"could not read People manifest {path}: {exc}") from exc


def decode_manifest(raw: bytes, source: str) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != PEOPLE_MANIFEST_SHA256:
        raise IntegrationError(
            f"{source}: manifest SHA-256 {digest} does not match pinned commit "
            f"{PEOPLE_ASSETS_COMMIT} ({PEOPLE_MANIFEST_SHA256})"
        )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrationError(f"{source}: invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise IntegrationError(f"{source}: expected a JSON object")
    return value


def validate_asset(person_id: int, key: str, value: object) -> dict:
    if not isinstance(value, dict):
        raise IntegrationError(f"TMDB Person {person_id}: missing or invalid {key} asset")

    path = value.get("path")
    url = value.get("url")
    sha256 = value.get("sha256")
    byte_count = value.get("bytes")
    width = value.get("width")
    height = value.get("height")
    asset_format = value.get("format")
    expected_relative_prefix = f"assets/people/{person_id}/"

    if not isinstance(path, str) or not path.startswith(expected_relative_prefix):
        raise IntegrationError(f"TMDB Person {person_id}: {key} has an invalid asset path")
    if not isinstance(url, str):
        raise IntegrationError(f"TMDB Person {person_id}: {key} is missing its URL")
    url_parts = urlsplit(url)
    expected_url_prefix = f"{ASSET_PATH_PREFIX}{person_id}/"
    if (
        url_parts.scheme != "https"
        or url_parts.netloc != ASSET_ORIGIN
        or not url_parts.path.startswith(expected_url_prefix)
        or url_parts.query
        or url_parts.fragment
    ):
        raise IntegrationError(f"TMDB Person {person_id}: {key} has an invalid canonical URL")
    if not isinstance(sha256, str) or not SHA256_RE.fullmatch(sha256):
        raise IntegrationError(f"TMDB Person {person_id}: {key} has an invalid SHA-256")
    if not is_positive_safe_integer(byte_count):
        raise IntegrationError(f"TMDB Person {person_id}: {key} has invalid byte metadata")
    if not is_positive_safe_integer(width) or not is_positive_safe_integer(height):
        raise IntegrationError(f"TMDB Person {person_id}: {key} has invalid dimensions")
    if asset_format not in {"png", "webp"}:
        raise IntegrationError(f"TMDB Person {person_id}: {key} has an invalid format")

    return {
        "url": url,
        "sha256": sha256,
    }


def validate_people_manifest(value: dict) -> tuple[dict[int, dict], dict[str, int]]:
    if value.get("schemaVersion") != PEOPLE_MANIFEST_SCHEMA_VERSION:
        raise IntegrationError(
            f"People manifest schemaVersion must be {PEOPLE_MANIFEST_SCHEMA_VERSION}"
        )
    people = value.get("people")
    record_count = value.get("recordCount")
    asset_counts = value.get("assetCounts")
    if not isinstance(people, list):
        raise IntegrationError("People manifest people must be an array")
    if record_count != len(people):
        raise IntegrationError(
            f"People manifest recordCount {record_count!r} does not match {len(people)} records"
        )
    if not isinstance(asset_counts, dict):
        raise IntegrationError("People manifest assetCounts must be an object")

    by_id: dict[int, dict] = {}
    calculated_asset_counts = {key: 0 for key in ALL_ASSET_KEYS}
    for index, record in enumerate(people):
        if not isinstance(record, dict):
            raise IntegrationError(f"People manifest record {index}: expected an object")
        person_id = record.get("tmdbPersonId")
        if not is_positive_safe_integer(person_id):
            raise IntegrationError(f"People manifest record {index}: invalid TMDB Person ID")
        if person_id in by_id:
            raise IntegrationError(f"People manifest contains duplicate TMDB Person ID {person_id}")

        canonical_name = record.get("canonicalName")
        if (
            not isinstance(canonical_name, str)
            or not canonical_name
            or canonical_name != canonical_name.strip()
        ):
            raise IntegrationError(f"TMDB Person {person_id}: invalid canonicalName")
        membership = record.get("categoryMembership")
        if (
            not isinstance(membership, list)
            or not membership
            or len(membership) != len(set(membership))
            or any(entry not in MEMBERSHIPS for entry in membership)
        ):
            raise IntegrationError(f"TMDB Person {person_id}: invalid categoryMembership")
        raw_assets = record.get("assets")
        if not isinstance(raw_assets, dict):
            raise IntegrationError(f"TMDB Person {person_id}: assets must be an object")

        assets: dict[str, dict] = {}
        for key in CORE_ASSET_KEYS:
            assets[key] = validate_asset(person_id, key, raw_assets.get(key))
            calculated_asset_counts[key] += 1

        has_focus_poster = "focusPoster" in raw_assets
        has_focus_landscape = "focusLandscape" in raw_assets
        if has_focus_poster != has_focus_landscape:
            raise IntegrationError(f"TMDB Person {person_id}: focus assets must be an all-or-nothing pair")
        if has_focus_poster:
            for key in FOCUS_ASSET_KEYS:
                assets[key] = validate_asset(person_id, key, raw_assets.get(key))
                calculated_asset_counts[key] += 1

        by_id[person_id] = {
            "tmdbPersonId": person_id,
            "canonicalName": canonical_name,
            "categoryMembership": membership,
            "assets": assets,
        }

    for key, count in calculated_asset_counts.items():
        if asset_counts.get(key) != count:
            raise IntegrationError(
                f"People manifest assetCounts.{key}={asset_counts.get(key)!r}; expected {count}"
            )
    return by_id, calculated_asset_counts


def load_category_people(config: dict) -> list[dict]:
    path = config["peoplePath"]
    value = load_json_file(path)
    if value.get("schemaVersion") != 1:
        raise IntegrationError(f"{path}: schemaVersion must be 1")
    if value.get("awardBodyId") != "academy-awards":
        raise IntegrationError(f"{path}: awardBodyId must be academy-awards")
    if value.get("categoryId") != config["categoryId"]:
        raise IntegrationError(
            f"{path}: categoryId must be {config['categoryId']}"
        )
    if value.get("status") != "winner":
        raise IntegrationError(f"{path}: status must be winner")
    people = value.get("people")
    if not isinstance(people, list):
        raise IntegrationError(f"{path}: people must be an array")

    validated: list[dict] = []
    seen_ids: set[int] = set()
    for index, person in enumerate(people):
        if not isinstance(person, dict):
            raise IntegrationError(f"{path}: people[{index}] must be an object")
        name = person.get("name")
        person_id = person.get("tmdbPersonId")
        if not isinstance(name, str) or not name or name != name.strip():
            raise IntegrationError(f"{path}: people[{index}] has an invalid name")
        if not is_positive_safe_integer(person_id):
            raise IntegrationError(f"{path}: people[{index}] has an invalid TMDB Person ID")
        if person_id in seen_ids:
            raise IntegrationError(f"{path}: duplicate TMDB Person ID {person_id}")
        seen_ids.add(person_id)
        validated.append({"name": name, "tmdbPersonId": person_id})
    return validated


def audit_category(config: dict, people: list[dict], by_id: dict[int, dict]) -> dict:
    missing_people: list[dict] = []
    membership_mismatches: list[dict] = []
    incomplete_core_artwork: list[dict] = []
    missing_focus_pairs: list[dict] = []
    canonical_name_differences: list[dict] = []

    for person in people:
        person_id = person["tmdbPersonId"]
        record = by_id.get(person_id)
        if record is None:
            missing_people.append(person)
            continue
        if config["requiredMembership"] not in record["categoryMembership"]:
            membership_mismatches.append(
                {
                    **person,
                    "categoryMembership": record["categoryMembership"],
                }
            )
        missing_core = [key for key in CORE_ASSET_KEYS if key not in record["assets"]]
        if missing_core:
            incomplete_core_artwork.append({**person, "missingAssets": missing_core})
        if any(key not in record["assets"] for key in FOCUS_ASSET_KEYS):
            missing_focus_pairs.append(person)
        if person["name"] != record["canonicalName"]:
            canonical_name_differences.append(
                {
                    "tmdbPersonId": person_id,
                    "awardsName": person["name"],
                    "canonicalName": record["canonicalName"],
                }
            )

    return {
        "categoryId": config["categoryId"],
        "sourceType": config["sourceType"],
        "requiredMembership": config["requiredMembership"],
        "peopleOutput": config["peoplePath"].relative_to(REPO_ROOT).as_posix(),
        "uniquePeopleCount": len(people),
        "resolvedPeopleCount": len(people) - len(missing_people),
        "correctMembershipCount": len(people) - len(missing_people) - len(membership_mismatches),
        "completeCoreArtworkCount": len(people) - len(missing_people) - len(incomplete_core_artwork),
        "completeFocusPairCount": len(people) - len(missing_people) - len(missing_focus_pairs),
        "missingPeople": missing_people,
        "membershipMismatches": membership_mismatches,
        "incompleteCoreArtwork": incomplete_core_artwork,
        "missingFocusPairs": missing_focus_pairs,
        "canonicalNameDifferences": canonical_name_differences,
    }


def sample_resolution(
    sample: dict,
    category_people: dict[str, list[dict]],
    by_id: dict[int, dict],
) -> dict:
    category_id = sample["categoryId"]
    person_id = sample["tmdbPersonId"]
    config = next(item for item in CATEGORIES if item["categoryId"] == category_id)
    person = next(
        (item for item in category_people[category_id] if item["tmdbPersonId"] == person_id),
        None,
    )
    record = by_id.get(person_id)
    if person is None or record is None:
        raise IntegrationError(
            f"sample {category_id} TMDB Person {person_id} is not fully resolvable"
        )
    return {
        "categoryId": category_id,
        "sourceType": config["sourceType"],
        "awardsName": person["name"],
        "tmdbPersonId": person_id,
        "canonicalName": record["canonicalName"],
        "categoryMembership": record["categoryMembership"],
        "assets": {
            key: record["assets"][key]
            for key in ALL_ASSET_KEYS
            if key in record["assets"]
        },
    }


def build_report(manifest: dict) -> dict:
    by_id, asset_counts = validate_people_manifest(manifest)
    category_people = {
        config["categoryId"]: load_category_people(config) for config in CATEGORIES
    }
    coverage = [
        audit_category(config, category_people[config["categoryId"]], by_id)
        for config in CATEGORIES
    ]

    category_ids_by_person: dict[int, list[str]] = {}
    for config in CATEGORIES:
        for person in category_people[config["categoryId"]]:
            category_ids_by_person.setdefault(person["tmdbPersonId"], []).append(
                config["categoryId"]
            )
    unique_ids = sorted(category_ids_by_person)
    resolved_unique_count = sum(person_id in by_id for person_id in unique_ids)
    shared_ids = [
        person_id
        for person_id, category_ids in category_ids_by_person.items()
        if len(category_ids) > 1
    ]
    complete = all(
        not item["missingPeople"]
        and not item["membershipMismatches"]
        and not item["incompleteCoreArtwork"]
        for item in coverage
    )

    return {
        "schemaVersion": 1,
        "issue": 17,
        "identityKey": "tmdbPersonId",
        "peopleAssets": {
            "repository": PEOPLE_ASSETS_REPOSITORY,
            "commit": PEOPLE_ASSETS_COMMIT,
            "pinnedManifestUrl": PINNED_MANIFEST_URL,
            "runtimeManifestUrl": RUNTIME_MANIFEST_URL,
            "manifestSha256": PEOPLE_MANIFEST_SHA256,
            "manifestSchemaVersion": PEOPLE_MANIFEST_SCHEMA_VERSION,
            "manifestRecordCount": len(by_id),
            "manifestAssetCounts": asset_counts,
        },
        "builder": {
            "repository": BUILDER_REPOSITORY,
            "migrationCommit": BUILDER_MIGRATION_COMMIT,
            "verifiedBaselineCommit": BUILDER_VERIFIED_BASELINE_COMMIT,
            "resolution": "numeric TMDB Person ID through the canonical People manifest",
            "constructsLegacyPeopleUrls": False,
        },
        "combinedCoverage": {
            "categoryPersonCount": sum(len(items) for items in category_people.values()),
            "uniqueAwardsPeopleCount": len(unique_ids),
            "resolvedUniqueAwardsPeopleCount": resolved_unique_count,
            "peopleSharedAcrossAwardCategoriesCount": len(shared_ids),
            "complete": complete and resolved_unique_count == len(unique_ids),
        },
        "categoryCoverage": coverage,
        "sampleResolutions": [
            sample_resolution(sample, category_people, by_id) for sample in SAMPLES
        ],
        "fallback": {
            "whenManifestRecordMissing": (
                "Preserve the TMDB Person identity and use the Builder's TMDB profile "
                "artwork fallback, then the person emoji when no profile is available."
            ),
            "legacyPeopleUrlFallback": False,
            "canonicalAwardResultDependsOnArtwork": False,
        },
    }


def validate_acceptance(report: dict) -> None:
    if not report["combinedCoverage"]["complete"]:
        raise IntegrationError("Awards People artwork coverage is incomplete")


def render_report(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def check_report(expected: str) -> None:
    try:
        current = REPORT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise IntegrationError(f"could not read {REPORT_PATH}: {exc}") from exc
    if current != expected:
        raise IntegrationError(
            "People artwork integration report is out of date; run "
            "scripts/check_people_artwork_integration.py"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--people-manifest",
        default=PINNED_MANIFEST_URL,
        help=(
            "Local path or HTTPS URL for the exact pinned People manifest. "
            "Defaults to the commit-pinned production GitHub raw URL."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed Issue #17 integration report is out of date.",
    )
    args = parser.parse_args()

    try:
        raw_manifest = load_manifest_bytes(args.people_manifest)
        manifest = decode_manifest(raw_manifest, args.people_manifest)
        report = build_report(manifest)
        validate_acceptance(report)
        rendered = render_report(report)
        if args.check:
            check_report(rendered)
            print(
                "Awards People artwork integration is valid: "
                f"{report['combinedCoverage']['resolvedUniqueAwardsPeopleCount']}/"
                f"{report['combinedCoverage']['uniqueAwardsPeopleCount']} unique people resolved."
            )
            return 0

        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(rendered, encoding="utf-8")
        print(
            f"Wrote {REPORT_PATH} with "
            f"{report['combinedCoverage']['resolvedUniqueAwardsPeopleCount']} resolved people."
        )
        return 0
    except IntegrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
