#!/usr/bin/env python3
"""Generate and validate Golden Globes movie and series catalogues."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "data" / "awards" / "golden-globes" / "results"
CATEGORIES_PATH = REPO_ROOT / "data" / "awards" / "golden-globes" / "categories.json"
CONTRACTS_PATH = REPO_ROOT / "data" / "awards" / "golden-globes" / "output-contracts.json"
CATALOG_ROOT = REPO_ROOT / "catalog"
IMDB_RE = re.compile(r"^tt\d+$")
POSTER_TEMPLATE = "https://images.metahub.space/poster/medium/{imdb_id}/img"
TMDB_POSTER_RE = re.compile(r"^https://image\.tmdb\.org/t/p/w500/[A-Za-z0-9_-]+\.jpg$")


class OutputError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OutputError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise OutputError(f"{path}: expected a JSON object")
    return value


def collect_rows() -> tuple[dict[str, list[dict]], set[str]]:
    categories = load_json(CATEGORIES_PATH).get("categories", [])
    category_ids = {category["id"] for category in categories}
    rows: dict[str, list[dict]] = defaultdict(list)
    files = sorted(RESULTS_DIR.glob("*.json"))
    if len(files) != 83:
        raise OutputError(f"expected 83 Golden Globes ceremony files, found {len(files)}")
    for path in files:
        payload = load_json(path)
        ceremony = payload.get("ceremony", {})
        number = ceremony.get("number")
        if not isinstance(number, int):
            raise OutputError(f"{path}: invalid ceremony number")
        for result_index, result in enumerate(payload.get("results", [])):
            if result.get("status") != "winner":
                continue
            category_id = result.get("categoryId")
            if category_id not in category_ids:
                raise OutputError(f"{path}: unknown category {category_id!r}")
            works = result.get("works") or ([result["work"]] if "work" in result else [])
            for work_index, work in enumerate(works):
                rows[category_id].append(
                    {
                        "ceremony": number,
                        "resultIndex": result_index,
                        "workIndex": work_index,
                        "work": work,
                    }
                )
    return rows, category_ids


def build_outputs() -> tuple[dict[Path, str], list[dict]]:
    rows_by_category, category_ids = collect_rows()
    contract_payload = load_json(CONTRACTS_PATH)
    poster_overrides = contract_payload.get("posterOverrides", {})
    known_unavailable_posters = contract_payload.get("knownUnavailablePosters", [])
    if (
        not isinstance(poster_overrides, dict)
        or any(not IMDB_RE.fullmatch(key) for key in poster_overrides)
        or any(
            not isinstance(value, str) or not TMDB_POSTER_RE.fullmatch(value)
            for value in poster_overrides.values()
        )
    ):
        raise OutputError(f"{CONTRACTS_PATH}: posterOverrides is invalid")
    if (
        not isinstance(known_unavailable_posters, list)
        or len(known_unavailable_posters) != len(set(known_unavailable_posters))
        or any(not isinstance(value, str) or not IMDB_RE.fullmatch(value) for value in known_unavailable_posters)
        or set(known_unavailable_posters) & set(poster_overrides)
    ):
        raise OutputError(f"{CONTRACTS_PATH}: knownUnavailablePosters is invalid")
    contracts = contract_payload.get("categories")
    if not isinstance(contracts, list):
        raise OutputError(f"{CONTRACTS_PATH}: categories must be an array")
    contract_ids = [contract.get("categoryId") for contract in contracts]
    if len(contract_ids) != len(set(contract_ids)) or set(contract_ids) != category_ids:
        raise OutputError("output contracts must cover every Golden Globes category exactly once")

    outputs: dict[Path, str] = {}
    manifest_catalogs: list[dict] = []
    published_imdb_ids: set[str] = set()
    for contract in contracts:
        category_id = contract["categoryId"]
        rows = rows_by_category.get(category_id, [])
        result_count = sum(
            1
            for path in RESULTS_DIR.glob("*.json")
            for result in load_json(path).get("results", [])
            if result.get("status") == "winner" and result.get("categoryId") == category_id
        )
        ceremonies = [row["ceremony"] for row in rows]
        actual = {
            "firstCeremony": min(ceremonies) if ceremonies else None,
            "lastCeremony": max(ceremonies) if ceremonies else None,
            "expectedResults": result_count,
            "expectedWorkLinks": len(rows),
        }
        expected = {
            field: contract[field]
            for field in ("firstCeremony", "lastCeremony", "expectedResults", "expectedWorkLinks")
        }
        if actual != expected:
            raise OutputError(
                f"{category_id}: aggregate contract mismatch; expected={expected}, actual={actual}"
            )

        catalogs = contract.get("catalogs")
        if not isinstance(catalogs, list):
            raise OutputError(f"{category_id}: catalogs must be an array")
        contracted_media = {catalog["mediaType"] for catalog in catalogs}
        actual_media = {row["work"].get("mediaType") for row in rows}
        if catalogs:
            if actual_media != contracted_media:
                raise OutputError(
                    f"{category_id}: media contract mismatch; expected={contracted_media}, actual={actual_media}"
                )
        elif actual_media != {"podcast"}:
            raise OutputError(f"{category_id}: a catalogue-compatible media type is not published")

        for catalog in catalogs:
            media_type = catalog["mediaType"]
            media_rows = [row for row in rows if row["work"].get("mediaType") == media_type]
            media_rows.sort(
                key=lambda row: (-row["ceremony"], row["resultIndex"], row["workIndex"])
            )
            if len(media_rows) != catalog["expectedWorkLinks"]:
                raise OutputError(
                    f"{catalog['id']}: expected {catalog['expectedWorkLinks']} work links, "
                    f"found {len(media_rows)}"
                )
            seen: set[str] = set()
            metas = []
            for row in media_rows:
                work = row["work"]
                imdb_id = work.get("imdbId")
                title = work.get("title")
                if not isinstance(imdb_id, str) or not IMDB_RE.fullmatch(imdb_id):
                    raise OutputError(f"{category_id}: {title!r} has no valid IMDb title ID")
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
    configured_posters = set(poster_overrides) | set(known_unavailable_posters)
    if not configured_posters <= published_imdb_ids:
        raise OutputError(
            f"{CONTRACTS_PATH}: poster configuration contains unpublished IMDb IDs "
            f"{sorted(configured_posters - published_imdb_ids)}"
        )
    return outputs, manifest_catalogs


def write_outputs(outputs: dict[Path, str]) -> None:
    expected = set(outputs)
    for media_type in ("movie", "series"):
        directory = CATALOG_ROOT / media_type
        if directory.is_dir():
            for path in directory.glob("golden-globes-*.json"):
                if path not in expected:
                    path.unlink()
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_outputs(outputs: dict[Path, str]) -> None:
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
        for path in (CATALOG_ROOT / media_type).glob("golden-globes-*.json")
    }
    if actual != expected:
        raise OutputError(
            "Golden Globes catalogue file set differs from the output contracts"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        outputs, manifest_catalogs = build_outputs()
        if args.check:
            check_outputs(outputs)
        else:
            write_outputs(outputs)
        movie_count = sum(catalog["type"] == "movie" for catalog in manifest_catalogs)
        series_count = len(manifest_catalogs) - movie_count
        verb = "valid" if args.check else "written"
        print(
            f"Golden Globes outputs are {verb}: {movie_count} movie catalogues and "
            f"{series_count} series catalogues."
        )
        return 0
    except (OutputError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
