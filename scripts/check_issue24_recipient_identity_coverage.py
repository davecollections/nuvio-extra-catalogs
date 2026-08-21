#!/usr/bin/env python3
"""Build the Issue #24 recipient identity and People artwork coverage report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from check_people_artwork_integration import (
    PEOPLE_ASSETS_COMMIT,
    PEOPLE_ASSETS_REPOSITORY,
    PEOPLE_MANIFEST_SHA256,
    PINNED_MANIFEST_URL,
    RUNTIME_MANIFEST_URL,
    decode_manifest,
    load_manifest_bytes,
    validate_people_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "data" / "awards" / "academy-awards" / "results"
REPORT_PATH = REPO_ROOT / "reports" / "issue-24-academy-recipient-identity-coverage.json"
SOURCE_COMMIT = "c5e9716b7e020e70205d6b95f5a5678526c1b45f"

BASELINE_CATEGORY_IDS = {
    "best-actor",
    "best-actress",
    "best-supporting-actor",
    "best-supporting-actress",
    "best-director",
}
ISSUE24_CATEGORY_IDS = (
    "adapted-screenplay",
    "animated-feature-film",
    "animated-short-film",
    "casting",
    "cinematography",
    "costume-design",
    "documentary-feature-film",
    "documentary-short-film",
    "film-editing",
    "international-feature-film",
    "live-action-short-film",
    "makeup-and-hairstyling",
    "original-score",
    "original-screenplay",
    "original-song",
    "production-design",
    "sound",
    "visual-effects",
)


class CoverageError(RuntimeError):
    pass


def load_results() -> list[dict]:
    results: list[dict] = []
    files = sorted(RESULTS_DIR.glob("*.json"))
    if len(files) != 98:
        raise CoverageError(f"expected 98 ceremony files, found {len(files)}")
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CoverageError(f"{path}: invalid JSON: {exc}") from exc
        ceremony = payload.get("ceremony", {}).get("number")
        for result in payload.get("results", []):
            if isinstance(result, dict):
                results.append({"ceremony": ceremony, **result})
    return results


def build_report(manifest: dict) -> dict:
    people_assets, asset_counts = validate_people_manifest(manifest)
    results = load_results()
    baseline_tmdb_ids = {
        person["tmdbId"]
        for result in results
        if result.get("categoryId") in BASELINE_CATEGORY_IDS
        for person in result.get("people", [])
        if isinstance(person.get("tmdbId"), int)
    }

    identities_by_imdb: dict[str, dict] = {}
    category_summary: dict[str, dict] = {
        category_id: {
            "categoryId": category_id,
            "winnerResultCount": 0,
            "personLinkCount": 0,
            "uniqueImdbPeople": set(),
            "uniqueTmdbPeople": set(),
            "unresolvedTmdbPeople": set(),
        }
        for category_id in ISSUE24_CATEGORY_IDS
    }
    for result in results:
        category_id = result.get("categoryId")
        if category_id not in category_summary or result.get("status") != "winner":
            continue
        summary = category_summary[category_id]
        summary["winnerResultCount"] += 1
        for person in result.get("people", []):
            imdb_id = person.get("imdbId")
            name = person.get("name")
            tmdb_id = person.get("tmdbId")
            if not isinstance(imdb_id, str) or not isinstance(name, str):
                raise CoverageError(
                    f"{category_id}: every preserved Issue #24 person must have a name and IMDb Person ID"
                )
            summary["personLinkCount"] += 1
            summary["uniqueImdbPeople"].add(imdb_id)
            if isinstance(tmdb_id, int):
                summary["uniqueTmdbPeople"].add(tmdb_id)
            else:
                summary["unresolvedTmdbPeople"].add(imdb_id)

            identity = identities_by_imdb.setdefault(
                imdb_id,
                {
                    "name": name,
                    "imdbPersonId": imdb_id,
                    "tmdbPersonId": tmdb_id if isinstance(tmdb_id, int) else None,
                    "categoryIds": set(),
                },
            )
            if identity["name"] != name:
                raise CoverageError(
                    f"IMDb Person ID {imdb_id} maps to {identity['name']!r} and {name!r}"
                )
            if identity["tmdbPersonId"] is not None and tmdb_id is not None and identity["tmdbPersonId"] != tmdb_id:
                raise CoverageError(f"IMDb Person ID {imdb_id} maps to multiple TMDB Person IDs")
            if identity["tmdbPersonId"] is None and isinstance(tmdb_id, int):
                identity["tmdbPersonId"] = tmdb_id
            identity["categoryIds"].add(category_id)

    identities: list[dict] = []
    for identity in identities_by_imdb.values():
        tmdb_id = identity["tmdbPersonId"]
        asset_record = people_assets.get(tmdb_id) if isinstance(tmdb_id, int) else None
        identities.append(
            {
                "name": identity["name"],
                "imdbPersonId": identity["imdbPersonId"],
                **({"tmdbPersonId": tmdb_id} if isinstance(tmdb_id, int) else {}),
                "categoryIds": sorted(identity["categoryIds"]),
                "alreadyCoveredByV05": tmdb_id in baseline_tmdb_ids if isinstance(tmdb_id, int) else False,
                "peopleAssetPresent": asset_record is not None,
                "peopleAssetMembership": asset_record["categoryMembership"] if asset_record else [],
            }
        )
    identities.sort(key=lambda item: (item["name"].casefold(), item["imdbPersonId"]))

    new_resolved_ids = {
        item["tmdbPersonId"]
        for item in identities
        if "tmdbPersonId" in item and not item["alreadyCoveredByV05"]
    }
    new_asset_ids = {
        item["tmdbPersonId"]
        for item in identities
        if "tmdbPersonId" in item
        and not item["alreadyCoveredByV05"]
        and item["peopleAssetPresent"]
    }
    unresolved = [item for item in identities if "tmdbPersonId" not in item]

    category_coverage: list[dict] = []
    for category_id in ISSUE24_CATEGORY_IDS:
        summary = category_summary[category_id]
        category_coverage.append(
            {
                "categoryId": category_id,
                "winnerResultCount": summary["winnerResultCount"],
                "personLinkCount": summary["personLinkCount"],
                "uniqueImdbPeopleCount": len(summary["uniqueImdbPeople"]),
                "uniqueTmdbPeopleCount": len(summary["uniqueTmdbPeople"]),
                "unresolvedTmdbPeopleCount": len(summary["unresolvedTmdbPeople"]),
                "nativePeopleOutputPublished": False,
                "peopleArtworkRequired": False,
            }
        )

    return {
        "schemaVersion": 1,
        "issue": 24,
        "identityKeys": ["imdbPersonId", "tmdbPersonId"],
        "reconciliationSource": {
            "repository": "https://github.com/DLu/oscar_data",
            "commit": SOURCE_COMMIT,
        },
        "peopleAssets": {
            "repository": PEOPLE_ASSETS_REPOSITORY,
            "commit": PEOPLE_ASSETS_COMMIT,
            "pinnedManifestUrl": PINNED_MANIFEST_URL,
            "runtimeManifestUrl": RUNTIME_MANIFEST_URL,
            "manifestSha256": PEOPLE_MANIFEST_SHA256,
            "manifestRecordCount": len(people_assets),
            "manifestAssetCounts": asset_counts,
        },
        "coverage": {
            "categoryCount": len(ISSUE24_CATEGORY_IDS),
            "uniqueImdbRecipientCount": len(identities),
            "tmdbResolvedRecipientCount": len(identities) - len(unresolved),
            "unresolvedTmdbRecipientCount": len(unresolved),
            "newTmdbRecipientCount": len(new_resolved_ids),
            "newTmdbRecipientsWithPeopleAssetsCount": len(new_asset_ids),
            "newTmdbRecipientsWithoutPeopleAssetsCount": len(new_resolved_ids - new_asset_ids),
            "requiredPeopleArtworkGapCount": 0,
        },
        "nativeOutputAssessment": {
            "newNativePeopleOutputs": [],
            "reason": (
                "Issue #24 publishes winner-film catalogues only. Nuvio renders movie artwork for "
                "these catalogues, and the current canonical People manifest exposes actor/director "
                "memberships rather than the new craft recipient roles. Recipient identities are "
                "preserved for future compatible sources, but People artwork is not a publication gate."
            ),
            "peopleArtworkHandoffRequired": False,
        },
        "categoryCoverage": category_coverage,
        "identities": identities,
    }


def render_report(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        raw = load_manifest_bytes(PINNED_MANIFEST_URL)
        manifest = decode_manifest(raw, PINNED_MANIFEST_URL)
        report = build_report(manifest)
        rendered = render_report(report)
        if args.check:
            try:
                current = REPORT_PATH.read_text(encoding="utf-8")
            except OSError as exc:
                raise CoverageError(f"could not read {REPORT_PATH}: {exc}") from exc
            if current != rendered:
                raise CoverageError(
                    "Issue #24 recipient identity report is out of date; run "
                    "scripts/check_issue24_recipient_identity_coverage.py"
                )
        else:
            REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            REPORT_PATH.write_text(rendered, encoding="utf-8")
        status = "valid" if args.check else "written"
        print(
            f"Issue #24 recipient identity coverage is {status}: "
            f"{report['coverage']['uniqueImdbRecipientCount']} IMDb identities, "
            f"{report['coverage']['tmdbResolvedRecipientCount']} TMDB-resolved, "
            f"{report['coverage']['unresolvedTmdbRecipientCount']} unresolved, "
            "0 required artwork gaps."
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
