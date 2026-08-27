#!/usr/bin/env python3
"""Generate narrowly scoped static metadata fallbacks for BAFTA Television."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bafta_artwork import published_titles
from bafta_common import ROOT, load_json
from bafta_metadata import (
    TELEVISION_CONFIG,
    contracted_fallback_ids,
    reviewed_metadata_identities,
)


MANIFEST_PATH = ROOT / "manifest.json"
META_ROOT = ROOT / "meta"
MEDIA_TYPES = ("movie", "series")
DESCRIPTION = (
    "Reviewed award-catalogue title. This compact record is supplied "
    "when installed metadata providers do not return the title."
)


class FallbackError(RuntimeError):
    """Raised when static metadata fallbacks cannot be reproduced safely."""


def expected_outputs() -> tuple[dict[Path, str], list]:
    config = TELEVISION_CONFIG
    titles = published_titles(config)
    identities = reviewed_metadata_identities(config)
    contracts = load_json(config.contracts_path)
    fallback_ids = contracted_fallback_ids(config)
    unavailable_posters = contracts.get("knownUnavailablePosters")
    if not isinstance(unavailable_posters, list):
        raise FallbackError(
            f"{config.contracts_path}: knownUnavailablePosters must be an array"
        )
    unavailable = set(unavailable_posters)
    if not set(fallback_ids) <= set(titles):
        raise FallbackError("metadata fallback contract contains unpublished IMDb IDs")

    outputs: dict[Path, str] = {}
    fallback_types: set[str] = set()
    for imdb_id in fallback_ids:
        title = titles[imdb_id]
        identity = identities.get(imdb_id)
        if not isinstance(identity, dict):
            raise FallbackError(f"{imdb_id}: no reviewed identity")
        media_type = title.get("mediaType")
        if media_type not in MEDIA_TYPES or identity.get("mediaType") != media_type:
            raise FallbackError(f"{imdb_id}: conflicting media type")
        meta = {
            "id": imdb_id,
            "type": media_type,
            "name": title.get("title"),
        }
        if imdb_id not in unavailable:
            catalog_ids = title.get("catalogIds")
            if not isinstance(catalog_ids, list) or not catalog_ids:
                raise FallbackError(f"{imdb_id}: no source catalogue")
            source_path = (
                ROOT / "catalog" / media_type / f"{catalog_ids[0]}.json"
            )
            source = load_json(source_path)
            matching = [
                item
                for item in source.get("metas", [])
                if isinstance(item, dict) and item.get("id") == imdb_id
            ]
            if len(matching) != 1:
                raise FallbackError(
                    f"{source_path}: expected one preview for {imdb_id}"
                )
            meta["poster"] = matching[0].get("poster")
            meta["posterShape"] = matching[0].get("posterShape")
        meta["releaseInfo"] = str(identity["releaseYear"])
        meta["description"] = DESCRIPTION
        if not isinstance(meta.get("name"), str) or not meta["name"].strip():
            raise FallbackError(f"{imdb_id}: invalid title")
        if "poster" in meta and (
            not isinstance(meta["poster"], str)
            or not meta["poster"].startswith("https://")
            or meta.get("posterShape") != "poster"
        ):
            raise FallbackError(f"{imdb_id}: invalid poster fallback")
        path = META_ROOT / media_type / f"{imdb_id}.json"
        outputs[path] = json.dumps({"meta": meta}, ensure_ascii=False, indent=2) + "\n"
        fallback_types.add(media_type)

    resources = [
        "catalog",
        {
            "name": "meta",
            "types": [value for value in MEDIA_TYPES if value in fallback_types],
            "idPrefixes": fallback_ids,
        },
    ]
    return outputs, resources


def update_manifest(resources: list, *, check: bool) -> None:
    manifest = load_json(MANIFEST_PATH)
    if check:
        if manifest.get("resources") != resources:
            raise FallbackError(f"{MANIFEST_PATH}: metadata resource is stale")
        return
    manifest["resources"] = resources
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_outputs(outputs: dict[Path, str]) -> None:
    expected = set(outputs)
    for media_type in MEDIA_TYPES:
        root = META_ROOT / media_type
        if root.is_dir():
            for path in root.glob("*.json"):
                if path not in expected:
                    path.unlink()
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_outputs(outputs: dict[Path, str]) -> None:
    expected = set(outputs)
    actual = {
        path
        for media_type in MEDIA_TYPES
        for path in (META_ROOT / media_type).glob("*.json")
    }
    if actual != expected:
        raise FallbackError("static metadata fallback file set is stale")
    for path, content in outputs.items():
        if path.read_text(encoding="utf-8") != content:
            raise FallbackError(f"{path}: generated fallback is stale")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        outputs, resources = expected_outputs()
        if args.check:
            check_outputs(outputs)
        else:
            write_outputs(outputs)
        update_manifest(resources, check=args.check)
        movie_count = sum(path.parent.name == "movie" for path in outputs)
        series_count = len(outputs) - movie_count
        verb = "valid" if args.check else "written"
        print(
            f"BAFTA Television static metadata fallbacks are {verb}: "
            f"{movie_count} movie and {series_count} series routes."
        )
        return 0
    except (FallbackError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
