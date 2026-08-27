#!/usr/bin/env python3
"""Generate award-level static manifest presets and their catalogue routes."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_MANIFEST_PATH = REPO_ROOT / "manifest.json"
PRESETS_ROOT = REPO_ROOT / "presets"


class PresetError(RuntimeError):
    pass


@dataclass(frozen=True)
class Preset:
    slug: str
    addon_id: str
    name: str
    description: str
    catalogue_prefix: str

    @property
    def root(self) -> Path:
        return PRESETS_ROOT / self.slug


PRESETS = (
    Preset(
        "academy",
        "com.davecollections.nuvio.extra.academy",
        "Xtra — Academy Awards",
        "Independent Xtra preset with complete Academy Awards winning-film catalogues for Nuvio and other compatible clients.",
        "academy-",
    ),
    Preset(
        "golden-globes",
        "com.davecollections.nuvio.extra.goldenglobes",
        "Xtra — Golden Globes",
        "Independent Xtra preset with complete Golden Globes film and television winner catalogues for Nuvio and other compatible clients.",
        "golden-globes-",
    ),
    Preset(
        "bafta-film",
        "com.davecollections.nuvio.extra.baftafilm",
        "Xtra — BAFTA Film Awards",
        "Independent Xtra preset with complete BAFTA Film winner catalogues for Nuvio and other compatible clients.",
        "bafta-film-",
    ),
    Preset(
        "bafta-television",
        "com.davecollections.nuvio.extra.baftatelevision",
        "Xtra — BAFTA Television Awards",
        "Independent Xtra preset with complete BAFTA Television film and series winner catalogues for Nuvio and other compatible clients.",
        "bafta-television-",
    ),
)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PresetError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PresetError(f"{path}: expected a JSON object")
    return value


def expected_preset(preset: Preset, root_manifest: dict) -> tuple[str, dict[Path, Path]]:
    catalogs = [
        catalog
        for catalog in root_manifest.get("catalogs", [])
        if catalog.get("id", "").startswith(preset.catalogue_prefix)
    ]
    if not catalogs:
        raise PresetError(f"{preset.slug}: no matching catalogues in root manifest")
    types = [
        media_type
        for media_type in ("movie", "series")
        if any(catalog.get("type") == media_type for catalog in catalogs)
    ]
    resources: list = ["catalog"]
    copies = {
        preset.root / "catalog" / catalog["type"] / f"{catalog['id']}.json":
        REPO_ROOT / "catalog" / catalog["type"] / f"{catalog['id']}.json"
        for catalog in catalogs
    }
    published_ids: set[str] = set()
    for source in copies.values():
        payload = load_json(source)
        metas = payload.get("metas")
        if not isinstance(metas, list):
            raise PresetError(f"{source}: expected a metas array")
        published_ids.update(
            meta["id"]
            for meta in metas
            if isinstance(meta, dict) and isinstance(meta.get("id"), str)
        )
    root_meta_resources = [
        resource
        for resource in root_manifest.get("resources", [])
        if isinstance(resource, dict) and resource.get("name") == "meta"
    ]
    if len(root_meta_resources) > 1:
        raise PresetError("root manifest declares multiple meta resources")
    if root_meta_resources:
        root_meta_ids = root_meta_resources[0].get("idPrefixes")
        if not isinstance(root_meta_ids, list):
            raise PresetError("root meta resource has no idPrefixes array")
        meta_ids = [imdb_id for imdb_id in root_meta_ids if imdb_id in published_ids]
        if meta_ids:
            meta_types: set[str] = set()
            for imdb_id in meta_ids:
                matches = [
                    media_type
                    for media_type in ("movie", "series")
                    if (REPO_ROOT / "meta" / media_type / f"{imdb_id}.json").is_file()
                ]
                if len(matches) != 1:
                    raise PresetError(
                        f"{imdb_id}: expected one root static metadata route"
                    )
                media_type = matches[0]
                meta_types.add(media_type)
                copies[
                    preset.root / "meta" / media_type / f"{imdb_id}.json"
                ] = REPO_ROOT / "meta" / media_type / f"{imdb_id}.json"
            resources.append(
                {
                    "name": "meta",
                    "types": [
                        media_type
                        for media_type in ("movie", "series")
                        if media_type in meta_types
                    ],
                    "idPrefixes": meta_ids,
                }
            )
    manifest = {
        "id": preset.addon_id,
        "version": root_manifest["version"],
        "name": preset.name,
        "description": preset.description,
        "resources": resources,
        "types": types,
        "catalogs": catalogs,
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", copies


def write_preset(preset: Preset, manifest_text: str, copies: dict[Path, Path]) -> None:
    manifest_path = preset.root / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest_text, encoding="utf-8")
    expected = set(copies)
    for resource_name in ("catalog", "meta"):
        resource_root = preset.root / resource_name
        if resource_root.is_dir():
            for path in resource_root.rglob("*.json"):
                if path not in expected:
                    path.unlink()
    for destination, source in copies.items():
        if not source.is_file():
            raise PresetError(f"missing root catalogue {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def check_preset(preset: Preset, manifest_text: str, copies: dict[Path, Path]) -> None:
    manifest_path = preset.root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.read_text(encoding="utf-8") != manifest_text:
        raise PresetError(f"{manifest_path}: preset manifest is stale")
    actual = set((preset.root / "catalog").rglob("*.json")) | set(
        (preset.root / "meta").rglob("*.json")
    )
    if actual != set(copies):
        raise PresetError(f"{preset.slug}: preset resource file set is stale")
    for destination, source in copies.items():
        if destination.read_bytes() != source.read_bytes():
            raise PresetError(f"{destination}: does not byte-match {source}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        root_manifest = load_json(ROOT_MANIFEST_PATH)
        for preset in PRESETS:
            manifest_text, copies = expected_preset(preset, root_manifest)
            if args.check:
                check_preset(preset, manifest_text, copies)
            else:
                write_preset(preset, manifest_text, copies)
        verb = "valid" if args.check else "written"
        print(
            f"Award-level manifest presets are {verb}: "
            + ", ".join(preset.slug for preset in PRESETS)
            + "."
        )
        return 0
    except (PresetError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
