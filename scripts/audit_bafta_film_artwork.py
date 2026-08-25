#!/usr/bin/env python3
"""Audit published BAFTA Film posters through the production artwork path.

MetaHub-by-IMDb remains the default catalogue poster source. This maintenance
tool checks every unique published BAFTA Film IMDb title with the same live URL
used by the add-on. For MetaHub 404s only, it consults the already-reviewed
TMDB identity and records whether a TMDB poster can be used as an explicit
fallback. Award facts and work identities are never inferred from artwork.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bafta_common import ROOT, SOURCE_DIR, load_json
from enrich_bafta_identities import api_json
from enrich_golden_globes_identities import IdentityError


MANIFEST_PATH = ROOT / "manifest.json"
IDENTITY_MAP_PATH = SOURCE_DIR / "identity-map.json"
CONTRACTS_PATH = ROOT / "data" / "awards" / "bafta-film" / "output-contracts.json"
REPORT_PATH = ROOT / "reports" / "bafta-film-artwork-audit.json"
POSTER_TEMPLATE = "https://images.metahub.space/poster/medium/{imdb_id}/img"
TMDB_IMAGE_TEMPLATE = "https://image.tmdb.org/t/p/w500{poster_path}"
TOKEN_ENV = "TMDB_API_READ_TOKEN"


class ArtworkError(RuntimeError):
    """Raised when the live artwork audit cannot produce trustworthy evidence."""


def published_titles() -> dict[str, dict]:
    manifest = load_json(MANIFEST_PATH)
    titles: dict[str, dict] = {}
    for catalog in manifest.get("catalogs", []):
        catalog_id = catalog.get("id")
        media_type = catalog.get("type")
        if not isinstance(catalog_id, str) or not catalog_id.startswith("bafta-film-"):
            continue
        path = ROOT / "catalog" / str(media_type) / f"{catalog_id}.json"
        payload = load_json(path)
        for meta in payload.get("metas", []):
            imdb_id = meta.get("id")
            if not isinstance(imdb_id, str):
                raise ArtworkError(f"{path}: published meta has no IMDb ID")
            current = titles.setdefault(
                imdb_id,
                {
                    "imdbId": imdb_id,
                    "title": meta.get("name"),
                    "mediaType": media_type,
                    "catalogIds": [],
                },
            )
            if current["mediaType"] != media_type:
                raise ArtworkError(f"{imdb_id}: published as conflicting media types")
            current["catalogIds"].append(catalog_id)
    if not titles:
        raise ArtworkError("manifest contains no BAFTA Film catalogues")
    for entry in titles.values():
        entry["catalogIds"].sort()
    return titles


def reviewed_identities() -> dict[str, dict]:
    identity_map = load_json(IDENTITY_MAP_PATH)
    by_imdb: dict[str, dict] = {}
    for entry in identity_map.get("works", []):
        resolution = entry.get("resolution")
        if not isinstance(resolution, dict) or "film" not in entry.get("programmes", []):
            continue
        imdb_id = resolution.get("imdbId")
        if not isinstance(imdb_id, str):
            continue
        identity = {
            "workKey": entry.get("key"),
            "tmdbId": resolution.get("tmdbId"),
            "mediaType": resolution.get("mediaType"),
        }
        existing = by_imdb.get(imdb_id)
        if existing is not None and existing != identity:
            raise ArtworkError(f"{imdb_id}: conflicting reviewed BAFTA Film identities")
        by_imdb[imdb_id] = identity
    return by_imdb


def check_metahub(imdb_id: str) -> dict:
    url = POSTER_TEMPLATE.format(imdb_id=imdb_id)
    last_error: Exception | None = None
    for attempt in range(3):
        request = Request(url, method="HEAD", headers={"User-Agent": "Xtra-BAFTA-artwork-audit/1.0"})
        try:
            with urlopen(request, timeout=20) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "")
            if status == 200 and content_type.startswith("image/"):
                return {"status": status, "contentType": content_type, "url": url}
            raise ArtworkError(
                f"{imdb_id}: MetaHub returned HTTP {status} with {content_type or 'no content type'}"
            )
        except HTTPError as exc:
            if exc.code == 404:
                return {"status": 404, "contentType": exc.headers.get("Content-Type", ""), "url": url}
            last_error = exc
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(0.5 * (2**attempt))
    raise ArtworkError(f"{imdb_id}: MetaHub request failed after retries: {last_error}")


def tmdb_fallback(imdb_id: str, identity: dict, token: str) -> dict:
    tmdb_id = identity.get("tmdbId")
    media_type = identity.get("mediaType")
    if not isinstance(tmdb_id, int) or media_type not in {"movie", "series"}:
        return {
            "tmdbId": tmdb_id if isinstance(tmdb_id, int) else None,
            "mediaType": media_type,
            "posterPath": None,
            "posterUrl": None,
            "fallbackNote": "The reviewed IMDb-only identity has no TMDB relationship.",
        }
    tmdb_type = "tv" if media_type == "series" else "movie"
    details = api_json(f"/{tmdb_type}/{tmdb_id}", token, {"language": "en-US"})
    poster_path = details.get("poster_path")
    return {
        "tmdbId": tmdb_id,
        "mediaType": media_type,
        "posterPath": poster_path if isinstance(poster_path, str) else None,
        "posterUrl": (
            TMDB_IMAGE_TEMPLATE.format(poster_path=poster_path)
            if isinstance(poster_path, str)
            else None
        ),
        "fallbackNote": (
            "TMDB supplies an explicit poster fallback."
            if isinstance(poster_path, str)
            else "The reviewed TMDB title has no poster."
        ),
    }


def audit(workers: int) -> dict:
    titles = published_titles()
    identities = reviewed_identities()
    missing_identity = sorted(set(titles) - set(identities))
    if missing_identity:
        raise ArtworkError(f"published IMDb IDs lack reviewed identities: {missing_identity}")

    checks: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_metahub, imdb_id): imdb_id for imdb_id in titles}
        for completed, future in enumerate(as_completed(futures), start=1):
            imdb_id = futures[future]
            checks[imdb_id] = future.result()
            if completed % 100 == 0 or completed == len(futures):
                print(f"Checked {completed}/{len(futures)} MetaHub posters", file=sys.stderr)

    missing = sorted(imdb_id for imdb_id, result in checks.items() if result["status"] == 404)
    fallbacks: list[dict] = []
    if missing:
        token = os.environ.get(TOKEN_ENV)
        if not token:
            raise ArtworkError(f"{TOKEN_ENV} is required to review {len(missing)} MetaHub gaps")
        for imdb_id in missing:
            fallback = tmdb_fallback(imdb_id, identities[imdb_id], token)
            fallbacks.append({**titles[imdb_id], **identities[imdb_id], **fallback})

    contracts = load_json(CONTRACTS_PATH)
    configured_overrides = contracts.get("posterOverrides", {})
    configured_unavailable = contracts.get("knownUnavailablePosters", [])
    if not isinstance(configured_overrides, dict) or not isinstance(configured_unavailable, list):
        raise ArtworkError(f"{CONTRACTS_PATH}: invalid poster contract")

    expected_overrides = {
        entry["imdbId"]: entry["posterUrl"]
        for entry in fallbacks
        if entry["posterUrl"] is not None
    }
    expected_unavailable = sorted(
        entry["imdbId"] for entry in fallbacks if entry["posterUrl"] is None
    )
    return {
        "schemaVersion": 1,
        "awardBodyId": "bafta-film",
        "checkedAt": datetime.now(timezone.utc).date().isoformat(),
        "productionPosterTemplate": POSTER_TEMPLATE,
        "publishedUniqueTitleCount": len(titles),
        "metaHubAvailableCount": len(titles) - len(missing),
        "metaHubMissingCount": len(missing),
        "tmdbFallbackCount": len(expected_overrides),
        "knownUnavailableCount": len(expected_unavailable),
        "fallbackReview": fallbacks,
        "expectedContract": {
            "posterOverrides": dict(sorted(expected_overrides.items())),
            "knownUnavailablePosters": expected_unavailable,
        },
        "currentContractMatchesLiveReview": (
            configured_overrides == expected_overrides
            and sorted(configured_unavailable) == expected_unavailable
        ),
    }


def check_committed_report() -> dict:
    report = load_json(REPORT_PATH)
    titles = published_titles()
    contracts = load_json(CONTRACTS_PATH)
    expected_contract = {
        "posterOverrides": dict(sorted(contracts.get("posterOverrides", {}).items())),
        "knownUnavailablePosters": sorted(contracts.get("knownUnavailablePosters", [])),
    }
    if report.get("schemaVersion") != 1 or report.get("awardBodyId") != "bafta-film":
        raise ArtworkError(f"{REPORT_PATH}: invalid report identity")
    if report.get("productionPosterTemplate") != POSTER_TEMPLATE:
        raise ArtworkError(f"{REPORT_PATH}: production poster template differs")
    if report.get("publishedUniqueTitleCount") != len(titles):
        raise ArtworkError(f"{REPORT_PATH}: published title count differs")
    if report.get("expectedContract") != expected_contract:
        raise ArtworkError(f"{REPORT_PATH}: expected poster contract differs")
    if report.get("currentContractMatchesLiveReview") is not True:
        raise ArtworkError(f"{REPORT_PATH}: live review does not match the contract")

    fallback_review = report.get("fallbackReview")
    if not isinstance(fallback_review, list):
        raise ArtworkError(f"{REPORT_PATH}: fallback review must be an array")
    by_imdb = {
        entry.get("imdbId"): entry
        for entry in fallback_review
        if isinstance(entry, dict) and isinstance(entry.get("imdbId"), str)
    }
    if len(by_imdb) != len(fallback_review):
        raise ArtworkError(f"{REPORT_PATH}: duplicate or invalid fallback review IDs")
    expected_gap_ids = set(expected_contract["posterOverrides"]) | set(
        expected_contract["knownUnavailablePosters"]
    )
    if set(by_imdb) != expected_gap_ids or not expected_gap_ids <= set(titles):
        raise ArtworkError(f"{REPORT_PATH}: fallback review title set differs")
    for imdb_id, url in expected_contract["posterOverrides"].items():
        if by_imdb[imdb_id].get("posterUrl") != url:
            raise ArtworkError(f"{REPORT_PATH}: fallback URL differs for {imdb_id}")
    for imdb_id in expected_contract["knownUnavailablePosters"]:
        if by_imdb[imdb_id].get("posterUrl") is not None:
            raise ArtworkError(f"{REPORT_PATH}: unavailable title has a fallback URL")

    total = report.get("publishedUniqueTitleCount")
    available = report.get("metaHubAvailableCount")
    missing = report.get("metaHubMissingCount")
    fallback_count = report.get("tmdbFallbackCount")
    unavailable_count = report.get("knownUnavailableCount")
    if (
        not all(isinstance(value, int) for value in (total, available, missing, fallback_count, unavailable_count))
        or available + missing != total
        or fallback_count + unavailable_count != missing
        or fallback_count != len(expected_contract["posterOverrides"])
        or unavailable_count != len(expected_contract["knownUnavailablePosters"])
    ):
        raise ArtworkError(f"{REPORT_PATH}: artwork counts are inconsistent")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--check", action="store_true", help="fail if the committed report differs")
    parser.add_argument(
        "--offline-check",
        action="store_true",
        help="validate the committed report and contracts without network requests",
    )
    args = parser.parse_args()
    if args.check and args.offline_check:
        parser.error("--check and --offline-check are mutually exclusive")
    if args.workers < 1 or args.workers > 32:
        parser.error("--workers must be between 1 and 32")

    try:
        if args.offline_check:
            report = check_committed_report()
            print(
                "BAFTA Film artwork report is valid offline: "
                f"{report['metaHubAvailableCount']}/{report['publishedUniqueTitleCount']} "
                f"MetaHub posters, {report['tmdbFallbackCount']} TMDB fallbacks, "
                f"{report['knownUnavailableCount']} unavailable."
            )
            return 0
        report = audit(args.workers)
        rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.check:
            if not report["currentContractMatchesLiveReview"]:
                raise ArtworkError(
                    f"{CONTRACTS_PATH}: poster contract differs from the live review"
                )
            if not REPORT_PATH.exists() or REPORT_PATH.read_text(encoding="utf-8") != rendered:
                raise ArtworkError(f"{REPORT_PATH}: committed live audit report is out of date")
        else:
            REPORT_PATH.write_text(rendered, encoding="utf-8")
    except (ArtworkError, IdentityError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "BAFTA Film artwork audit complete: "
        f"{report['metaHubAvailableCount']}/{report['publishedUniqueTitleCount']} MetaHub posters, "
        f"{report['tmdbFallbackCount']} TMDB fallbacks, "
        f"{report['knownUnavailableCount']} unavailable."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
