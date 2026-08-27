"""Audit metadata-provider compatibility for published BAFTA catalogues."""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bafta_artwork import published_titles, reviewed_identities
from bafta_common import (
    ROOT,
    SOURCE_DIR,
    identity_in_current_programme,
    load_json,
)


NUVIO_MANIFEST_URL = "https://catalog.nuvio.tv/manifest.json"
NUVIO_META_TEMPLATE = "https://catalog.nuvio.tv/meta/{media_type}/{imdb_id}.json"
CINEMETA_MANIFEST_URL = "https://v3-cinemeta.strem.io/manifest.json"
CINEMETA_META_TEMPLATE = (
    "https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"
)


class MetadataError(RuntimeError):
    """Raised when metadata compatibility evidence is invalid or unavailable."""


@dataclass(frozen=True)
class MetadataConfig:
    programme: str
    award_body_id: str
    award_name: str
    catalogue_prefix: str

    @property
    def contracts_path(self) -> Path:
        return ROOT / "data" / "awards" / self.award_body_id / "output-contracts.json"

    @property
    def report_path(self) -> Path:
        return ROOT / "reports" / f"{self.award_body_id}-metadata-audit.json"


TELEVISION_CONFIG = MetadataConfig(
    programme="television",
    award_body_id="bafta-television",
    award_name="BAFTA Television",
    catalogue_prefix="bafta-television-",
)


def reviewed_metadata_identities(config: MetadataConfig) -> dict[str, dict]:
    identities = reviewed_identities(config)
    required_release_years = set(contracted_fallback_ids(config))
    identity_map = load_json(SOURCE_DIR / "identity-map.json")
    for entry in identity_map.get("works", []):
        resolution = entry.get("resolution")
        if not isinstance(resolution, dict) or not identity_in_current_programme(
            entry, config.programme
        ):
            continue
        imdb_id = resolution.get("imdbId")
        if (
            not isinstance(imdb_id, str)
            or imdb_id not in identities
            or imdb_id not in required_release_years
        ):
            continue
        release_year = resolution.get("releaseYear")
        if not isinstance(release_year, int):
            raise MetadataError(f"{imdb_id}: reviewed identity has no release year")
        existing_year = identities[imdb_id].get("releaseYear")
        if existing_year is not None and existing_year != release_year:
            raise MetadataError(f"{imdb_id}: conflicting reviewed release years")
        identities[imdb_id]["releaseYear"] = release_year
    missing_year = sorted(
        imdb_id
        for imdb_id in required_release_years
        if not isinstance(identities.get(imdb_id, {}).get("releaseYear"), int)
    )
    if missing_year:
        raise MetadataError(f"reviewed IMDb IDs lack release years: {missing_year}")
    return identities


def check_provider(
    provider_name: str,
    url_template: str,
    media_type: str,
    imdb_id: str,
) -> dict:
    url = url_template.format(media_type=media_type, imdb_id=imdb_id)
    last_error: Exception | None = None
    for attempt in range(3):
        request = Request(
            url,
            headers={"User-Agent": "Xtra-BAFTA-metadata-audit/1.0"},
        )
        try:
            with urlopen(request, timeout=25) as response:
                status = response.status
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise MetadataError(
                    f"{provider_name} returned an invalid meta response for {imdb_id}"
                )
            if not isinstance(payload.get("meta"), dict):
                return {
                    "status": status,
                    "resolved": False,
                    "reason": "missing-meta-object",
                    "url": url,
                }
            meta = payload["meta"]
            valid_name = isinstance(meta.get("name"), str) and bool(meta["name"].strip())
            resolved = (
                meta.get("id") == imdb_id
                and meta.get("type") == media_type
                and valid_name
            )
            reason = None
            if not resolved:
                if not meta:
                    reason = "empty-meta"
                elif meta.get("id") != imdb_id or meta.get("type") != media_type:
                    reason = "conflicting-identity"
                elif not valid_name:
                    reason = "missing-required-name"
                else:
                    reason = "invalid-meta"
            return {
                "status": status,
                "resolved": resolved,
                "reason": reason,
                "url": url,
            }
        except HTTPError as exc:
            if exc.code == 404:
                return {
                    "status": 404,
                    "resolved": False,
                    "reason": "http-404",
                    "url": url,
                }
            last_error = exc
        except (json.JSONDecodeError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(0.5 * (2**attempt))
    raise MetadataError(
        f"{provider_name} request failed for {imdb_id} after retries: {last_error}"
    )


def provider_checks(
    provider_name: str,
    url_template: str,
    titles: dict[str, dict],
    workers: int,
) -> dict[str, dict]:
    checks: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                check_provider,
                provider_name,
                url_template,
                title["mediaType"],
                imdb_id,
            ): imdb_id
            for imdb_id, title in titles.items()
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            imdb_id = futures[future]
            checks[imdb_id] = future.result()
            if completed % 100 == 0 or completed == len(futures):
                print(
                    f"Checked {completed}/{len(futures)} titles through {provider_name}",
                    file=sys.stderr,
                )
    return checks


def contracted_fallback_ids(config: MetadataConfig) -> list[str]:
    contracts = load_json(config.contracts_path)
    fallback_ids = contracts.get("metadataFallbackIds")
    if (
        not isinstance(fallback_ids, list)
        or any(not isinstance(value, str) for value in fallback_ids)
        or fallback_ids != sorted(set(fallback_ids))
    ):
        raise MetadataError(
            f"{config.contracts_path}: metadataFallbackIds must be a sorted unique array"
        )
    return fallback_ids


def audit(config: MetadataConfig, workers: int) -> dict:
    titles = published_titles(config)
    identities = reviewed_metadata_identities(config)
    missing_identity = sorted(set(titles) - set(identities))
    if missing_identity:
        raise MetadataError(
            f"published IMDb IDs lack reviewed identities: {missing_identity}"
        )

    nuvio_checks = provider_checks(
        "Nuvio official catalogue provider",
        NUVIO_META_TEMPLATE,
        titles,
        workers,
    )
    nuvio_gaps = {
        imdb_id: titles[imdb_id]
        for imdb_id, result in nuvio_checks.items()
        if not result["resolved"]
    }
    cinemeta_checks = provider_checks(
        "Cinemeta",
        CINEMETA_META_TEMPLATE,
        nuvio_gaps,
        workers,
    )

    fallback_review = []
    for imdb_id in sorted(nuvio_gaps):
        fallback_review.append(
            {
                **titles[imdb_id],
                **identities[imdb_id],
                "nuvio": nuvio_checks[imdb_id],
                "cinemeta": cinemeta_checks[imdb_id],
            }
        )

    fallback_ids = [entry["imdbId"] for entry in fallback_review]
    cinemeta_resolved = sum(
        entry["cinemeta"]["resolved"] for entry in fallback_review
    )
    expected_contract = {"metadataFallbackIds": fallback_ids}
    return {
        "schemaVersion": 1,
        "awardBodyId": config.award_body_id,
        "checkedAt": datetime.now(timezone.utc).date().isoformat(),
        "providers": {
            "nuvio": {
                "manifestUrl": NUVIO_MANIFEST_URL,
                "metaTemplate": NUVIO_META_TEMPLATE,
            },
            "cinemeta": {
                "manifestUrl": CINEMETA_MANIFEST_URL,
                "metaTemplate": CINEMETA_META_TEMPLATE,
            },
        },
        "publishedUniqueTitleCount": len(titles),
        "nuvioResolvedCount": len(titles) - len(fallback_review),
        "nuvioUnresolvedCount": len(fallback_review),
        "cinemetaResolvedAmongNuvioGapsCount": cinemeta_resolved,
        "unresolvedByEitherCount": len(fallback_review) - cinemeta_resolved,
        "fallbackReview": fallback_review,
        "expectedContract": expected_contract,
        "currentContractMatchesLiveReview": (
            contracted_fallback_ids(config) == fallback_ids
        ),
    }


def check_committed_report(config: MetadataConfig) -> dict:
    report = load_json(config.report_path)
    titles = published_titles(config)
    fallback_ids = contracted_fallback_ids(config)
    if (
        report.get("schemaVersion") != 1
        or report.get("awardBodyId") != config.award_body_id
    ):
        raise MetadataError(f"{config.report_path}: invalid report identity")
    if report.get("providers") != {
        "nuvio": {
            "manifestUrl": NUVIO_MANIFEST_URL,
            "metaTemplate": NUVIO_META_TEMPLATE,
        },
        "cinemeta": {
            "manifestUrl": CINEMETA_MANIFEST_URL,
            "metaTemplate": CINEMETA_META_TEMPLATE,
        },
    }:
        raise MetadataError(f"{config.report_path}: provider contract differs")
    if report.get("publishedUniqueTitleCount") != len(titles):
        raise MetadataError(f"{config.report_path}: published title count differs")
    if report.get("expectedContract") != {"metadataFallbackIds": fallback_ids}:
        raise MetadataError(f"{config.report_path}: fallback contract differs")
    if report.get("currentContractMatchesLiveReview") is not True:
        raise MetadataError(
            f"{config.report_path}: live review does not match the fallback contract"
        )

    review = report.get("fallbackReview")
    if not isinstance(review, list):
        raise MetadataError(f"{config.report_path}: fallbackReview must be an array")
    review_ids = [
        entry.get("imdbId") for entry in review if isinstance(entry, dict)
    ]
    if review_ids != fallback_ids or not set(fallback_ids) <= set(titles):
        raise MetadataError(f"{config.report_path}: fallback title set differs")
    for entry in review:
        imdb_id = entry["imdbId"]
        published = titles[imdb_id]
        if (
            entry.get("title") != published["title"]
            or entry.get("mediaType") != published["mediaType"]
            or entry.get("catalogIds") != published["catalogIds"]
        ):
            raise MetadataError(
                f"{config.report_path}: published identity differs for {imdb_id}"
            )
        nuvio = entry.get("nuvio")
        cinemeta = entry.get("cinemeta")
        if (
            not isinstance(nuvio, dict)
            or nuvio.get("resolved") is not False
            or not isinstance(cinemeta, dict)
            or not isinstance(cinemeta.get("resolved"), bool)
        ):
            raise MetadataError(
                f"{config.report_path}: invalid provider result for {imdb_id}"
            )

    total = report.get("publishedUniqueTitleCount")
    nuvio_resolved = report.get("nuvioResolvedCount")
    nuvio_unresolved = report.get("nuvioUnresolvedCount")
    cinemeta_resolved = report.get("cinemetaResolvedAmongNuvioGapsCount")
    unresolved_both = report.get("unresolvedByEitherCount")
    if (
        not all(
            isinstance(value, int)
            for value in (
                total,
                nuvio_resolved,
                nuvio_unresolved,
                cinemeta_resolved,
                unresolved_both,
            )
        )
        or nuvio_resolved + nuvio_unresolved != total
        or nuvio_unresolved != len(fallback_ids)
        or cinemeta_resolved + unresolved_both != nuvio_unresolved
        or cinemeta_resolved
        != sum(entry["cinemeta"]["resolved"] for entry in review)
    ):
        raise MetadataError(f"{config.report_path}: metadata counts are inconsistent")
    return report


def main(config: MetadataConfig) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument(
        "--check", action="store_true", help="fail if the committed report differs"
    )
    parser.add_argument(
        "--offline-check",
        action="store_true",
        help="validate committed evidence without network requests",
    )
    args = parser.parse_args()
    try:
        if args.workers < 1 or args.workers > 32:
            raise MetadataError("--workers must be between 1 and 32")
        if args.check and args.offline_check:
            raise MetadataError("--check and --offline-check are mutually exclusive")
        if args.offline_check:
            report = check_committed_report(config)
            print(
                f"{config.award_name} metadata evidence is valid: "
                f"{report['nuvioResolvedCount']} provider-resolved titles and "
                f"{report['nuvioUnresolvedCount']} contracted static fallbacks."
            )
            return 0

        report = audit(config, args.workers)
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if not report["currentContractMatchesLiveReview"]:
            raise MetadataError(
                f"{config.contracts_path}: metadata fallback contract differs from "
                "the live review"
            )
        if args.check:
            if (
                not config.report_path.is_file()
                or config.report_path.read_text(encoding="utf-8") != text
            ):
                raise MetadataError(
                    f"{config.report_path}: committed live audit report is out of date"
                )
            verb = "valid"
        else:
            config.report_path.parent.mkdir(parents=True, exist_ok=True)
            config.report_path.write_text(text, encoding="utf-8")
            verb = "written"
        print(
            f"{config.award_name} metadata audit is {verb}: "
            f"{report['nuvioResolvedCount']} provider-resolved titles, "
            f"{report['nuvioUnresolvedCount']} static fallbacks, and "
            f"{report['unresolvedByEitherCount']} unresolved by either reviewed provider."
        )
        return 0
    except (MetadataError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
