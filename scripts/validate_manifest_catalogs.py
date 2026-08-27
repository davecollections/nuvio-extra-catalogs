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
    "bafta-film": (REPO_ROOT / "presets" / "bafta-film", "bafta-film-"),
    "bafta-television": (
        REPO_ROOT / "presets" / "bafta-television",
        "bafta-television-",
    ),
}
MEDIA_TYPES = ("movie", "series")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
IMDB_RE = re.compile(r"^tt\d+$")
POSTER_TEMPLATE = "https://images.metahub.space/poster/medium/{imdb_id}/img"
POSTER_CONTRACT_PATHS = {
    "golden-globes-": REPO_ROOT
    / "data"
    / "awards"
    / "golden-globes"
    / "output-contracts.json",
    "bafta-film-": REPO_ROOT
    / "data"
    / "awards"
    / "bafta-film"
    / "output-contracts.json",
    "bafta-television-": REPO_ROOT
    / "data"
    / "awards"
    / "bafta-television"
    / "output-contracts.json",
}
FALLBACK_DESCRIPTION = (
    "Reviewed award-catalogue title. This compact record is supplied "
    "when installed metadata providers do not return the title."
)


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
) -> tuple[dict, list[tuple[str, str]], list[str]]:
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
    resources = manifest.get("resources")
    if not isinstance(resources, list) or not resources or resources[0] != "catalog":
        raise ValidationError(f"{path}: catalog must be the first resource")
    if len(resources) > 2:
        raise ValidationError(f"{path}: unsupported resource set")
    metadata_ids: list[str] = []
    if len(resources) == 2:
        meta_resource = resources[1]
        if not isinstance(meta_resource, dict) or set(meta_resource) != {
            "name",
            "types",
            "idPrefixes",
        }:
            raise ValidationError(f"{path}: meta resource shape is invalid")
        if meta_resource.get("name") != "meta":
            raise ValidationError(f"{path}: unsupported second resource")
        meta_types = meta_resource.get("types")
        if (
            not isinstance(meta_types, list)
            or not meta_types
            or meta_types
            != [media_type for media_type in MEDIA_TYPES if media_type in meta_types]
        ):
            raise ValidationError(f"{path}: meta resource types are invalid")
        metadata_ids = meta_resource.get("idPrefixes")
        if (
            not isinstance(metadata_ids, list)
            or not metadata_ids
            or any(
                not isinstance(imdb_id, str) or not IMDB_RE.fullmatch(imdb_id)
                for imdb_id in metadata_ids
            )
            or metadata_ids != sorted(set(metadata_ids))
        ):
            raise ValidationError(
                f"{path}: meta idPrefixes must be sorted exact IMDb IDs"
            )
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
    if len(resources) == 2 and any(
        media_type not in types for media_type in resources[1]["types"]
    ):
        raise ValidationError(f"{path}: meta resource type is not declared")
    return manifest, identities, metadata_ids


def validate_catalogue(
    path: Path,
    media_type: str,
    poster_overrides_by_prefix: dict[str, dict[str, str]],
) -> tuple[int, set[str]]:
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
        poster_overrides = next(
            (
                overrides
                for prefix, overrides in poster_overrides_by_prefix.items()
                if path.name.startswith(prefix)
            ),
            {},
        )
        expected_poster = poster_overrides.get(
            imdb_id, POSTER_TEMPLATE.format(imdb_id=imdb_id)
        )
        if meta.get("poster") != expected_poster:
            raise ValidationError(f"{path}: metas[{index}].poster is not the contracted URL")
        if meta.get("posterShape") != "poster":
            raise ValidationError(f"{path}: metas[{index}].posterShape must be poster")
    return len(value["metas"]), seen_ids


def metadata_files(root: Path) -> set[Path]:
    return {
        path
        for media_type in MEDIA_TYPES
        for path in (root / "meta" / media_type).glob("*.json")
    }


def validate_metadata_routes(
    root: Path,
    manifest: dict,
    metadata_ids: list[str],
    published_ids: dict[str, set[str]],
    poster_overrides: dict[str, str],
    unavailable_posters: set[str],
) -> set[Path]:
    meta_resource = next(
        (
            resource
            for resource in manifest["resources"]
            if isinstance(resource, dict) and resource.get("name") == "meta"
        ),
        None,
    )
    if not metadata_ids:
        if meta_resource is not None or metadata_files(root):
            raise ValidationError(f"{root}: unexpected static metadata routes")
        return set()
    if not isinstance(meta_resource, dict):
        raise ValidationError(f"{root}: metadata IDs lack a meta resource")

    expected: set[Path] = set()
    actual_types: set[str] = set()
    for imdb_id in metadata_ids:
        matching_types = [
            media_type
            for media_type in meta_resource["types"]
            if imdb_id in published_ids[media_type]
        ]
        if len(matching_types) != 1:
            raise ValidationError(
                f"{root}: {imdb_id} must match one published meta resource type"
            )
        media_type = matching_types[0]
        actual_types.add(media_type)
        path = root / "meta" / media_type / f"{imdb_id}.json"
        expected.add(path)
        payload = load_json(path)
        if set(payload) != {"meta"} or not isinstance(payload["meta"], dict):
            raise ValidationError(f"{path}: expected one meta object")
        meta = payload["meta"]
        required = {"id", "type", "name", "releaseInfo", "description"}
        optional_poster = {"poster", "posterShape"}
        if not required <= set(meta) or set(meta) - required not in (
            set(),
            optional_poster,
        ):
            raise ValidationError(f"{path}: static meta shape is invalid")
        if meta.get("id") != imdb_id or meta.get("type") != media_type:
            raise ValidationError(f"{path}: static meta identity differs")
        if not isinstance(meta.get("name"), str) or not meta["name"].strip():
            raise ValidationError(f"{path}: static meta name is invalid")
        if not isinstance(meta.get("releaseInfo"), str) or not re.fullmatch(
            r"\d{4}", meta["releaseInfo"]
        ):
            raise ValidationError(f"{path}: static meta releaseInfo is invalid")
        if meta.get("description") != FALLBACK_DESCRIPTION:
            raise ValidationError(f"{path}: static meta description differs")
        if imdb_id in unavailable_posters:
            if optional_poster & set(meta):
                raise ValidationError(
                    f"{path}: unavailable poster must be omitted from static meta"
                )
        else:
            expected_poster = poster_overrides.get(
                imdb_id, POSTER_TEMPLATE.format(imdb_id=imdb_id)
            )
            if (
                meta.get("poster") != expected_poster
                or meta.get("posterShape") != "poster"
            ):
                raise ValidationError(f"{path}: static meta poster differs")
    if actual_types != set(meta_resource["types"]):
        raise ValidationError(f"{root}: meta resource types differ from routes")
    if metadata_files(root) != expected:
        raise ValidationError(f"{root}: static metadata file set mismatch")
    return expected


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
        poster_overrides_by_prefix: dict[str, dict[str, str]] = {}
        all_poster_overrides: dict[str, str] = {}
        unavailable_posters: set[str] = set()
        for prefix, contracts_path in POSTER_CONTRACT_PATHS.items():
            contracts = load_json(contracts_path)
            poster_overrides = contracts.get("posterOverrides", {})
            if not isinstance(poster_overrides, dict):
                raise ValidationError(
                    f"{contracts_path}: posterOverrides must be an object"
                )
            poster_overrides_by_prefix[prefix] = poster_overrides
            for imdb_id, poster in poster_overrides.items():
                existing = all_poster_overrides.get(imdb_id)
                if existing is not None and existing != poster:
                    raise ValidationError(
                        f"{imdb_id}: conflicting poster override contracts"
                    )
                all_poster_overrides[imdb_id] = poster
            unavailable = contracts.get("knownUnavailablePosters", [])
            if not isinstance(unavailable, list):
                raise ValidationError(
                    f"{contracts_path}: knownUnavailablePosters must be an array"
                )
            unavailable_posters.update(unavailable)
        root_manifest, root_catalogs, root_metadata_ids = validate_manifest(
            ROOT_MANIFEST_PATH
        )
        root_files = catalogue_files(REPO_ROOT)
        if root_files != expected_files(REPO_ROOT, root_catalogs):
            raise ValidationError("root manifest/catalogue file set mismatch")
        total_items = 0
        root_published_ids = {media_type: set() for media_type in MEDIA_TYPES}
        for media_type, catalog_id in root_catalogs:
            count, imdb_ids = validate_catalogue(
                REPO_ROOT / "catalog" / media_type / f"{catalog_id}.json",
                media_type,
                poster_overrides_by_prefix,
            )
            total_items += count
            root_published_ids[media_type].update(imdb_ids)
        root_metadata_files = validate_metadata_routes(
            REPO_ROOT,
            root_manifest,
            root_metadata_ids,
            root_published_ids,
            all_poster_overrides,
            unavailable_posters,
        )

        addon_ids = {root_manifest["id"]}
        preset_catalog_union: set[tuple[str, str]] = set()
        for slug, (preset_root, required_prefix) in PRESETS.items():
            manifest_path = preset_root / "manifest.json"
            manifest, catalogs, metadata_ids = validate_manifest(
                manifest_path, required_prefix
            )
            if manifest["version"] != root_manifest["version"]:
                raise ValidationError(f"{manifest_path}: version differs from root manifest")
            if manifest["id"] in addon_ids:
                raise ValidationError(f"{manifest_path}: add-on ID is not unique")
            addon_ids.add(manifest["id"])
            files = catalogue_files(preset_root)
            if files != expected_files(preset_root, catalogs):
                raise ValidationError(f"{slug}: preset manifest/catalogue file set mismatch")
            preset_published_ids = {media_type: set() for media_type in MEDIA_TYPES}
            for media_type, catalog_id in catalogs:
                preset_path = preset_root / "catalog" / media_type / f"{catalog_id}.json"
                root_path = REPO_ROOT / "catalog" / media_type / f"{catalog_id}.json"
                if preset_path.read_bytes() != root_path.read_bytes():
                    raise ValidationError(f"{preset_path}: does not byte-match root catalogue")
                _, imdb_ids = validate_catalogue(
                    preset_path, media_type, poster_overrides_by_prefix
                )
                preset_published_ids[media_type].update(imdb_ids)
            preset_metadata_files = validate_metadata_routes(
                preset_root,
                manifest,
                metadata_ids,
                preset_published_ids,
                all_poster_overrides,
                unavailable_posters,
            )
            expected_metadata_ids = [
                imdb_id
                for imdb_id in root_metadata_ids
                if any(
                    imdb_id in preset_published_ids[media_type]
                    for media_type in MEDIA_TYPES
                )
            ]
            if metadata_ids != expected_metadata_ids:
                raise ValidationError(
                    f"{slug}: preset metadata routes differ from root manifest"
                )
            for preset_path in preset_metadata_files:
                relative = preset_path.relative_to(preset_root)
                root_path = REPO_ROOT / relative
                if root_path not in root_metadata_files:
                    raise ValidationError(
                        f"{preset_path}: route is absent from root manifest"
                    )
                if preset_path.read_bytes() != root_path.read_bytes():
                    raise ValidationError(
                        f"{preset_path}: does not byte-match root metadata"
                    )
            preset_catalog_union.update(catalogs)
        if preset_catalog_union != set(root_catalogs):
            raise ValidationError("award presets do not partition the all-awards manifest")

        movie_count = sum(media_type == "movie" for media_type, _ in root_catalogs)
        series_count = len(root_catalogs) - movie_count
        print(
            "Manifests and catalogues are valid: "
            f"{movie_count} movie and {series_count} series catalogues, "
            f"{total_items} total all-awards Meta Preview items, {len(PRESETS)} award presets."
        )
        return 0
    except (ValidationError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
