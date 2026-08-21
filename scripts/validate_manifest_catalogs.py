#!/usr/bin/env python3
"""Validate all-awards and award-preset manifests and static catalogues."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_MANIFEST_PATH = REPO_ROOT / "manifest.json"
PRESETS = {
    "academy": (REPO_ROOT / "presets" / "academy", "academy-"),
    "golden-globes": (REPO_ROOT / "presets" / "golden-globes", "golden-globes-"),
}
MEDIA_TYPES = ("movie", "series")
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


def validate_manifest(
    path: Path, required_prefix: str | None = None
) -> tuple[dict, list[tuple[str, str]]]:
    manifest = load_json(path)
    expected_keys = {"id", "version", "name", "description", "resources", "types", "catalogs"}
    if set(manifest) != expected_keys:
        raise ValidationError(f"{path}: manifest shape is invalid")
    if not isinstance(manifest.get("id"), str) or not manifest["id"].strip():
        raise ValidationError(f"{path}: id is invalid")
    if not isinstance(manifest.get("version"), str) or not SEMVER_RE.fullmatch(manifest["version"]):
        raise ValidationError(f"{path}: version must use semantic x.y.z form")
    if not isinstance(manifest.get("name"), str) or not manifest["name"].strip():
        raise ValidationError(f"{path}: name is invalid")
    if not isinstance(manifest.get("description"), str) or not manifest["description"].strip():
        raise ValidationError(f"{path}: description is invalid")
    if manifest.get("resources") != ["catalog"]:
        raise ValidationError(f"{path}: this add-on must remain catalog-only")
    types = manifest.get("types")
    if (
        not isinstance(types, list)
        or not types
        or any(media_type not in MEDIA_TYPES for media_type in types)
        or types != [media_type for media_type in MEDIA_TYPES if media_type in types]
    ):
        raise ValidationError(f"{path}: types must contain movie and/or series in canonical order")
    catalogs = manifest.get("catalogs")
    if not isinstance(catalogs, list) or not catalogs:
        raise ValidationError(f"{path}: catalogs must be a non-empty array")
    identities: list[tuple[str, str]] = []
    for index, catalog in enumerate(catalogs):
        if not isinstance(catalog, dict) or set(catalog) != {"type", "id", "name"}:
            raise ValidationError(f"{path}: catalogs[{index}] has an invalid shape")
        media_type = catalog.get("type")
        catalog_id = catalog.get("id")
        if media_type not in types:
            raise ValidationError(f"{path}: catalogs[{index}].type is not declared")
        if not isinstance(catalog_id, str) or not SLUG_RE.fullmatch(catalog_id):
            raise ValidationError(f"{path}: catalogs[{index}].id is invalid")
        if required_prefix and not catalog_id.startswith(required_prefix):
            raise ValidationError(f"{path}: catalogue {catalog_id!r} is outside this preset")
        if not isinstance(catalog.get("name"), str) or not catalog["name"].strip():
            raise ValidationError(f"{path}: catalogs[{index}].name is invalid")
        identity = (media_type, catalog_id)
        if identity in identities:
            raise ValidationError(f"{path}: duplicate catalogue {identity}")
        identities.append(identity)
    actual_types = [
        media_type for media_type in MEDIA_TYPES if any(item[0] == media_type for item in identities)
    ]
    if actual_types != types:
        raise ValidationError(f"{path}: types do not exactly match declared catalogues")
    return manifest, identities


def validate_catalogue(path: Path, media_type: str) -> int:
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
        if meta.get("type") != media_type:
            raise ValidationError(f"{path}: metas[{index}].type must be {media_type}")
        if not isinstance(meta.get("name"), str) or not meta["name"].strip():
            raise ValidationError(f"{path}: metas[{index}].name is invalid")
        if meta.get("poster") != POSTER_TEMPLATE.format(imdb_id=imdb_id):
            raise ValidationError(f"{path}: metas[{index}].poster is not the canonical MetaHub URL")
        if meta.get("posterShape") != "poster":
            raise ValidationError(f"{path}: metas[{index}].posterShape must be poster")
    return len(value["metas"])


def catalogue_files(root: Path) -> set[Path]:
    return {
        path
        for media_type in MEDIA_TYPES
        for path in (root / "catalog" / media_type).glob("*.json")
    }


def expected_files(root: Path, identities: list[tuple[str, str]]) -> set[Path]:
    return {
        root / "catalog" / media_type / f"{catalog_id}.json"
        for media_type, catalog_id in identities
    }


def main() -> int:
    try:
        root_manifest, root_catalogs = validate_manifest(ROOT_MANIFEST_PATH)
        root_files = catalogue_files(REPO_ROOT)
        if root_files != expected_files(REPO_ROOT, root_catalogs):
            raise ValidationError("root manifest/catalogue file set mismatch")
        total_items = sum(
            validate_catalogue(
                REPO_ROOT / "catalog" / media_type / f"{catalog_id}.json", media_type
            )
            for media_type, catalog_id in root_catalogs
        )

        addon_ids = {root_manifest["id"]}
        preset_catalog_union: set[tuple[str, str]] = set()
        for slug, (preset_root, required_prefix) in PRESETS.items():
            manifest_path = preset_root / "manifest.json"
            manifest, catalogs = validate_manifest(manifest_path, required_prefix)
            if manifest["version"] != root_manifest["version"]:
                raise ValidationError(f"{manifest_path}: version differs from root manifest")
            if manifest["id"] in addon_ids:
                raise ValidationError(f"{manifest_path}: add-on ID is not unique")
            addon_ids.add(manifest["id"])
            files = catalogue_files(preset_root)
            if files != expected_files(preset_root, catalogs):
                raise ValidationError(f"{slug}: preset manifest/catalogue file set mismatch")
            for media_type, catalog_id in catalogs:
                preset_path = preset_root / "catalog" / media_type / f"{catalog_id}.json"
                root_path = REPO_ROOT / "catalog" / media_type / f"{catalog_id}.json"
                if preset_path.read_bytes() != root_path.read_bytes():
                    raise ValidationError(f"{preset_path}: does not byte-match root catalogue")
                validate_catalogue(preset_path, media_type)
            preset_catalog_union.update(catalogs)
        if preset_catalog_union != set(root_catalogs):
            raise ValidationError("award presets do not partition the all-awards manifest")

        movie_count = sum(media_type == "movie" for media_type, _ in root_catalogs)
        series_count = len(root_catalogs) - movie_count
        print(
            "Manifests and catalogues are valid: "
            f"{movie_count} movie and {series_count} series catalogues, "
            f"{total_items} total all-awards Meta Preview items, 2 award presets."
        )
        return 0
    except (ValidationError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
