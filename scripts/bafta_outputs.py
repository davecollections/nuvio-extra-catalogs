"""Shared BAFTA catalogue generation and validation."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from build_golden_globes_outputs import (
    IMDB_RE,
    POSTER_TEMPLATE,
    TMDB_POSTER_RE,
    OutputError,
    load_json,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = ROOT / "catalog"


@dataclass(frozen=True)
class OutputConfig:
    award_body_id: str
    award_name: str
    catalogue_prefix: str
    expected_ceremony_files: int

    @property
    def body_dir(self) -> Path:
        return ROOT / "data" / "awards" / self.award_body_id

    @property
    def results_dir(self) -> Path:
        return self.body_dir / "results"

    @property
    def categories_path(self) -> Path:
        return self.body_dir / "categories.json"

    @property
    def contracts_path(self) -> Path:
        return self.body_dir / "output-contracts.json"


FILM_CONFIG = OutputConfig(
    award_body_id="bafta-film",
    award_name="BAFTA Film",
    catalogue_prefix="bafta-film-",
    expected_ceremony_files=78,
)

TELEVISION_CONFIG = OutputConfig(
    award_body_id="bafta-television",
    award_name="BAFTA Television",
    catalogue_prefix="bafta-television-",
    expected_ceremony_files=78,
)


def collect_rows(
    config: OutputConfig,
) -> tuple[dict[str, list[dict]], dict[str, int], set[str]]:
    categories = load_json(config.categories_path).get("categories", [])
    category_ids = {category["id"] for category in categories}
    rows: dict[str, list[dict]] = defaultdict(list)
    results: dict[str, int] = defaultdict(int)
    files = sorted(config.results_dir.glob("*.json"))
    if len(files) != config.expected_ceremony_files:
        raise OutputError(
            f"expected {config.expected_ceremony_files} {config.award_name} ceremony files, "
            f"found {len(files)}"
        )
    for path in files:
        payload = load_json(path)
        ceremony = payload.get("ceremony", {}).get("number")
        if not isinstance(ceremony, int):
            raise OutputError(f"{path}: invalid ceremony number")
        for result_index, result in enumerate(payload.get("results", [])):
            if result.get("status") != "winner":
                continue
            category_id = result.get("categoryId")
            if category_id not in category_ids:
                raise OutputError(f"{path}: unknown category {category_id!r}")
            results[category_id] += 1
            works = result.get("works") or (
                [result["work"]] if "work" in result else []
            )
            for work_index, work in enumerate(works):
                rows[category_id].append(
                    {
                        "ceremony": ceremony,
                        "resultIndex": result_index,
                        "workIndex": work_index,
                        "work": work,
                    }
                )
    return rows, results, category_ids


def validated_poster_contract(
    config: OutputConfig, payload: dict
) -> tuple[dict[str, str], list[str]]:
    overrides = payload.get("posterOverrides", {})
    unavailable = payload.get("knownUnavailablePosters", [])
    if (
        not isinstance(overrides, dict)
        or any(not IMDB_RE.fullmatch(key) for key in overrides)
        or any(
            not isinstance(value, str) or not TMDB_POSTER_RE.fullmatch(value)
            for value in overrides.values()
        )
    ):
        raise OutputError(f"{config.contracts_path}: posterOverrides is invalid")
    if (
        not isinstance(unavailable, list)
        or len(unavailable) != len(set(unavailable))
        or any(
            not isinstance(value, str) or not IMDB_RE.fullmatch(value)
            for value in unavailable
        )
        or set(unavailable) & set(overrides)
    ):
        raise OutputError(
            f"{config.contracts_path}: knownUnavailablePosters is invalid"
        )
    return overrides, unavailable


def build_outputs(config: OutputConfig) -> tuple[dict[Path, str], list[dict]]:
    rows_by_category, result_counts, category_ids = collect_rows(config)
    payload = load_json(config.contracts_path)
    if payload.get("awardBodyId") != config.award_body_id:
        raise OutputError(f"{config.contracts_path}: wrong award body")
    poster_overrides, unavailable_posters = validated_poster_contract(config, payload)
    contracts = payload.get("categories")
    if not isinstance(contracts, list):
        raise OutputError(f"{config.contracts_path}: categories must be an array")
    contract_ids = [contract.get("categoryId") for contract in contracts]
    if len(contract_ids) != len(set(contract_ids)) or set(contract_ids) != category_ids:
        raise OutputError(
            f"output contracts must cover every {config.award_name} category exactly once"
        )

    outputs: dict[Path, str] = {}
    manifest_catalogs: list[dict] = []
    published_imdb_ids: set[str] = set()
    for contract in contracts:
        category_id = contract["categoryId"]
        rows = rows_by_category.get(category_id, [])
        ceremonies = [row["ceremony"] for row in rows]
        actual = {
            "firstCeremony": min(ceremonies) if ceremonies else None,
            "lastCeremony": max(ceremonies) if ceremonies else None,
            "expectedResults": result_counts.get(category_id, 0),
            "expectedWorkLinks": len(rows),
        }
        expected = {
            field: contract[field]
            for field in (
                "firstCeremony",
                "lastCeremony",
                "expectedResults",
                "expectedWorkLinks",
            )
        }
        if actual != expected:
            raise OutputError(
                f"{category_id}: aggregate contract mismatch; "
                f"expected={expected}, actual={actual}"
            )

        catalogs = contract.get("catalogs")
        if not isinstance(catalogs, list) or not catalogs:
            raise OutputError(f"{category_id}: catalogs must be a non-empty array")
        non_catalogue_media = contract.get("nonCatalogueMedia", [])
        if not isinstance(non_catalogue_media, list):
            raise OutputError(f"{category_id}: nonCatalogueMedia must be an array")
        catalog_media = {catalog["mediaType"] for catalog in catalogs}
        omitted_media = {entry.get("mediaType") for entry in non_catalogue_media}
        if len(omitted_media) != len(non_catalogue_media) or catalog_media & omitted_media:
            raise OutputError(f"{category_id}: media output contracts overlap")
        for entry in non_catalogue_media:
            media_type = entry.get("mediaType")
            media_rows = [
                row for row in rows if row["work"].get("mediaType") == media_type
            ]
            if (
                media_type not in {"movie", "series"}
                or set(entry) != {"mediaType", "expectedWorkLinks"}
                or len(media_rows) != entry["expectedWorkLinks"]
                or any(IMDB_RE.fullmatch(str(row["work"].get("imdbId", ""))) for row in media_rows)
            ):
                raise OutputError(
                    f"{category_id}: invalid non-catalogue {media_type!r} contract"
                )
        expected_media = catalog_media | omitted_media
        actual_media = {row["work"].get("mediaType") for row in rows}
        if expected_media != actual_media:
            raise OutputError(
                f"{category_id}: media contract mismatch; "
                f"expected={expected_media}, actual={actual_media}"
            )

        for catalog in catalogs:
            media_type = catalog["mediaType"]
            media_rows = [
                row for row in rows if row["work"].get("mediaType") == media_type
            ]
            media_rows.sort(
                key=lambda row: (-row["ceremony"], row["resultIndex"], row["workIndex"])
            )
            if len(media_rows) != catalog["expectedWorkLinks"]:
                raise OutputError(
                    f"{catalog['id']}: expected {catalog['expectedWorkLinks']} work links, "
                    f"found {len(media_rows)}"
                )

            skipped = [
                row
                for row in media_rows
                if not IMDB_RE.fullmatch(str(row["work"].get("imdbId", "")))
            ]
            expected_skipped = catalog.get("expectedSkippedWorkLinks", 0)
            if len(skipped) != expected_skipped:
                raise OutputError(
                    f"{catalog['id']}: expected {expected_skipped} reviewed "
                    f"non-catalogue links, found {len(skipped)}"
                )

            seen: set[str] = set()
            metas = []
            for row in media_rows:
                work = row["work"]
                imdb_id = work.get("imdbId")
                if not isinstance(imdb_id, str) or not IMDB_RE.fullmatch(imdb_id):
                    continue
                title = work.get("title")
                if not isinstance(title, str) or not title.strip():
                    raise OutputError(f"{category_id}: work is missing its title")
                if imdb_id in seen:
                    continue
                seen.add(imdb_id)
                published_imdb_ids.add(imdb_id)
                metas.append(
                    {
                        "id": imdb_id,
                        "type": media_type,
                        "name": title.strip(),
                        "poster": poster_overrides.get(
                            imdb_id, POSTER_TEMPLATE.format(imdb_id=imdb_id)
                        ),
                        "posterShape": "poster",
                    }
                )
            if len(metas) != catalog["expectedItems"]:
                raise OutputError(
                    f"{catalog['id']}: expected {catalog['expectedItems']} unique items, "
                    f"found {len(metas)}"
                )
            path = CATALOG_ROOT / media_type / f"{catalog['id']}.json"
            outputs[path] = json.dumps(
                {"metas": metas}, ensure_ascii=False, separators=(",", ":")
            ) + "\n"
            manifest_catalogs.append(
                {"type": media_type, "id": catalog["id"], "name": catalog["name"]}
            )

    configured_posters = set(poster_overrides) | set(unavailable_posters)
    if not configured_posters <= published_imdb_ids:
        raise OutputError(
            f"{config.contracts_path}: poster configuration contains unpublished IMDb "
            f"IDs {sorted(configured_posters - published_imdb_ids)}"
        )
    return outputs, manifest_catalogs


def write_outputs(config: OutputConfig, outputs: dict[Path, str]) -> None:
    expected = set(outputs)
    for media_type in ("movie", "series"):
        directory = CATALOG_ROOT / media_type
        if directory.is_dir():
            for path in directory.glob(f"{config.catalogue_prefix}*.json"):
                if path not in expected:
                    path.unlink()
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_outputs(config: OutputConfig, outputs: dict[Path, str]) -> None:
    for path, expected in outputs.items():
        try:
            actual = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise OutputError(f"could not read {path}: {exc}") from exc
        if actual != expected:
            raise OutputError(f"{path}: generated catalogue is stale")
    expected = set(outputs)
    actual = {
        path
        for media_type in ("movie", "series")
        for path in (CATALOG_ROOT / media_type).glob(
            f"{config.catalogue_prefix}*.json"
        )
    }
    if actual != expected:
        raise OutputError(
            f"{config.award_name} catalogue file set differs from the output contracts"
        )


def main(config: OutputConfig) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        outputs, manifest_catalogs = build_outputs(config)
        if args.check:
            check_outputs(config, outputs)
        else:
            write_outputs(config, outputs)
        movie_count = sum(catalog["type"] == "movie" for catalog in manifest_catalogs)
        series_count = len(manifest_catalogs) - movie_count
        verb = "valid" if args.check else "written"
        print(
            f"{config.award_name} outputs are {verb}: {movie_count} movie catalogues "
            f"and {series_count} series catalogues."
        )
        return 0
    except (OutputError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
