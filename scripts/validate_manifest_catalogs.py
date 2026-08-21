#!/usr/bin/env python3
"""Validate the static manifest and every declared movie catalogue payload."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "manifest.json"
CATALOGUE_DIR = REPO_ROOT / "catalog" / "movie"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
IMDB_RE = re.compile(r"^tt\d+$")
POSTER_TEMPLATE = "https://images.metahub.space/poster/medium/{imdb_id}/img"


class ValidationError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected a JSON object")
    return value


def validate_manifest() -> list[str]:
    manifest = load_json(MANIFEST_PATH)
    if not isinstance(manifest.get("version"), str) or not SEMVER_RE.fullmatch(manifest["version"]):
        raise ValidationError(f"{MANIFEST_PATH}: version must use semantic x.y.z form")
    if manifest.get("resources") != ["catalog"]:
        raise ValidationError(f"{MANIFEST_PATH}: this add-on must remain catalog-only")
    if manifest.get("types") != ["movie"]:
        raise ValidationError(f"{MANIFEST_PATH}: types must contain only movie")
    catalogs = manifest.get("catalogs")
    if not isinstance(catalogs, list) or not catalogs:
        raise ValidationError(f"{MANIFEST_PATH}: catalogs must be a non-empty array")
    ids: list[str] = []
    for index, catalog in enumerate(catalogs):
        if not isinstance(catalog, dict) or set(catalog) != {"type", "id", "name"}:
            raise ValidationError(f"{MANIFEST_PATH}: catalogs[{index}] has an invalid shape")
        catalog_id = catalog.get("id")
        if catalog.get("type") != "movie":
            raise ValidationError(f"{MANIFEST_PATH}: catalogs[{index}].type must be movie")
        if not isinstance(catalog_id, str) or not SLUG_RE.fullmatch(catalog_id):
            raise ValidationError(f"{MANIFEST_PATH}: catalogs[{index}].id is invalid")
        if not isinstance(catalog.get("name"), str) or not catalog["name"].strip():
            raise ValidationError(f"{MANIFEST_PATH}: catalogs[{index}].name is invalid")
        if catalog_id in ids:
            raise ValidationError(f"{MANIFEST_PATH}: duplicate catalogue ID {catalog_id}")
        ids.append(catalog_id)
    return ids


def validate_catalogue(catalog_id: str) -> int:
    path = CATALOGUE_DIR / f"{catalog_id}.json"
    value = load_json(path)
    if set(value) != {"metas"} or not isinstance(value["metas"], list):
        raise ValidationError(f"{path}: expected one metas array")
    seen_ids: set[str] = set()
    for index, meta in enumerate(value["metas"]):
        if not isinstance(meta, dict) or set(meta) != {"id", "type", "name", "poster", "posterShape"}:
            raise ValidationError(f"{path}: metas[{index}] has an invalid Meta Preview shape")
        imdb_id = meta.get("id")
        if not isinstance(imdb_id, str) or not IMDB_RE.fullmatch(imdb_id):
            raise ValidationError(f"{path}: metas[{index}].id must be an IMDb tt ID")
        if imdb_id in seen_ids:
            raise ValidationError(f"{path}: duplicate IMDb ID {imdb_id}")
        seen_ids.add(imdb_id)
        if meta.get("type") != "movie":
            raise ValidationError(f"{path}: metas[{index}].type must be movie")
        if not isinstance(meta.get("name"), str) or not meta["name"].strip():
            raise ValidationError(f"{path}: metas[{index}].name is invalid")
        if meta.get("poster") != POSTER_TEMPLATE.format(imdb_id=imdb_id):
            raise ValidationError(f"{path}: metas[{index}].poster is not the canonical MetaHub URL")
        if meta.get("posterShape") != "poster":
            raise ValidationError(f"{path}: metas[{index}].posterShape must be poster")
    return len(value["metas"])


def main() -> int:
    try:
        manifest_ids = validate_manifest()
        files = sorted(CATALOGUE_DIR.glob("*.json"))
        file_ids = [path.stem for path in files]
        if set(file_ids) != set(manifest_ids):
            missing = sorted(set(manifest_ids) - set(file_ids))
            extra = sorted(set(file_ids) - set(manifest_ids))
            raise ValidationError(
                f"manifest/catalogue file mismatch; missing={missing}, extra={extra}"
            )
        total_items = sum(validate_catalogue(catalog_id) for catalog_id in manifest_ids)
        print(
            f"Manifest and catalogues are valid: {len(manifest_ids)} declared movie "
            f"catalogues, {total_items} total Meta Preview items."
        )
        return 0
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
