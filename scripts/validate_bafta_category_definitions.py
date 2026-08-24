#!/usr/bin/env python3
"""Validate stable BAFTA category IDs and source-to-work extraction rules."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "sources" / "bafta"
DEFINITIONS_PATH = SOURCE_DIR / "category-definitions.json"
REGISTRY_PATH = SOURCE_DIR / "current-category-pages.json"
DECISIONS_PATH = SOURCE_DIR / "lineage-decisions.json"
EXPECTED_PROGRAMMES = ("film", "television", "television-craft")
SNAPSHOTS = {
    "film": SOURCE_DIR / "winners-film.json",
    "television": SOURCE_DIR / "winners-television.json",
    "television-craft": SOURCE_DIR / "winners-television-craft.json",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MEDIA_TYPES = {"movie", "mixed"}
RECIPIENT_KINDS = {"work", "person", "team"}
CREDIT_ROLES = {
    "actor",
    "director",
    "writer",
    "composer",
    "cinematographer",
    "editor",
    "other",
}
WORK_FIELDS = {"heading", "details"}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def exact_keys(value: dict, required: set[str], allowed: set[str], label: str) -> None:
    missing = sorted(required - value.keys())
    extra = sorted(value.keys() - allowed)
    require(not missing, f"{label}: missing keys {missing}")
    require(not extra, f"{label}: unsupported keys {extra}")


def main() -> None:
    definitions = load_json(DEFINITIONS_PATH)
    registry = load_json(REGISTRY_PATH)
    decisions = load_json(DECISIONS_PATH)
    exact_keys(
        definitions,
        {"schemaVersion", "awardBodyId", "programmes", "sourceOverrides"},
        {"schemaVersion", "awardBodyId", "programmes", "sourceOverrides"},
        "category definitions",
    )
    require(definitions["schemaVersion"] == 1, "category definitions schemaVersion must be 1")
    require(definitions["awardBodyId"] == "bafta", "category definitions awardBodyId must be bafta")

    registry_by_id = {programme["id"]: programme for programme in registry["programmes"]}
    decisions_by_id = {programme["id"]: programme for programme in decisions["programmes"]}
    programmes = definitions["programmes"]
    require(
        [programme.get("id") for programme in programmes] == list(EXPECTED_PROGRAMMES),
        "category definitions programmes must use deterministic order",
    )

    definitions_by_programme: dict[str, dict[str, dict]] = {}
    all_ids: set[str] = set()
    for programme in programmes:
        programme_id = programme["id"]
        exact_keys(programme, {"id", "categories"}, {"id", "categories"}, programme_id)
        categories = programme["categories"]
        require(isinstance(categories, list) and categories, f"{programme_id}: categories must be non-empty")
        expected_names = [entry["name"] for entry in registry_by_id[programme_id]["included"]]
        require(
            [entry.get("name") for entry in categories] == expected_names,
            f"{programme_id}: definitions must exactly follow the current included registry",
        )
        by_name: dict[str, dict] = {}
        for category in categories:
            label = f"{programme_id}/{category.get('name')}"
            exact_keys(
                category,
                {"id", "name", "mediaType", "recipientKind", "workField"},
                {"id", "name", "mediaType", "recipientKind", "creditRole", "workField"},
                label,
            )
            category_id = category["id"]
            require(isinstance(category_id, str) and SLUG_RE.fullmatch(category_id), f"{label}: invalid ID")
            require(category_id.startswith(f"{programme_id}-"), f"{label}: ID must use programme prefix")
            require(category_id not in all_ids, f"duplicate BAFTA category ID {category_id}")
            require(category["mediaType"] in MEDIA_TYPES, f"{label}: invalid mediaType")
            expected_media_type = "movie" if programme_id == "film" else "mixed"
            require(category["mediaType"] == expected_media_type, f"{label}: unexpected mediaType")
            require(category["recipientKind"] in RECIPIENT_KINDS, f"{label}: invalid recipientKind")
            require(category["workField"] in WORK_FIELDS, f"{label}: invalid workField")
            if "creditRole" in category:
                require(category["creditRole"] in CREDIT_ROLES, f"{label}: invalid creditRole")
            require(category["name"] not in by_name, f"{programme_id}: duplicate category name")
            all_ids.add(category_id)
            by_name[category["name"]] = category
        definitions_by_programme[programme_id] = by_name

    source_mapping: dict[tuple[str, str], dict] = {}
    for programme_id in EXPECTED_PROGRAMMES:
        for name, category in definitions_by_programme[programme_id].items():
            source_mapping[(programme_id, name)] = category
        for decision in decisions_by_id[programme_id]["decisions"]:
            if decision["disposition"] != "current-lineage":
                continue
            target_programme = decision.get("currentProgramme", programme_id)
            target_name = decision["currentCategory"]
            category = definitions_by_programme[target_programme].get(target_name)
            require(category is not None, f"{programme_id}/{decision['label']}: target definition is missing")
            key = (programme_id, decision["label"])
            require(key not in source_mapping, f"duplicate source mapping for {programme_id}/{decision['label']}")
            source_mapping[key] = category

    overrides = definitions["sourceOverrides"]
    require(isinstance(overrides, list), "sourceOverrides must be an array")
    require(
        [(entry.get("programme"), entry.get("label", "").casefold()) for entry in overrides]
        == sorted((entry.get("programme"), entry.get("label", "").casefold()) for entry in overrides),
        "sourceOverrides must be sorted by programme and label",
    )
    override_fields: dict[tuple[str, str], str] = {}
    for entry in overrides:
        exact_keys(entry, {"programme", "label", "workField"}, {"programme", "label", "workField"}, "source override")
        key = (entry["programme"], entry["label"])
        require(key in source_mapping, f"source override has no included mapping: {key}")
        require(key not in override_fields, f"duplicate source override: {key}")
        require(entry["workField"] in WORK_FIELDS, f"source override has invalid workField: {key}")
        require(
            entry["workField"] != source_mapping[key]["workField"],
            f"source override is redundant: {key}",
        )
        override_fields[key] = entry["workField"]

    selected_results = 0
    work_references = 0
    selected_by_programme: dict[str, int] = {}
    for programme_id, snapshot_path in SNAPSHOTS.items():
        snapshot = load_json(snapshot_path)
        selected = 0
        for winner in snapshot["winners"]:
            key = (programme_id, winner["category"])
            category = source_mapping.get(key)
            if category is None:
                continue
            field = override_fields.get(key, category["workField"])
            if field == "heading":
                values = [winner.get("heading")]
            else:
                values = winner.get("details")
            require(isinstance(values, list) and values, f"{programme_id}/{winner['nominationId']}: no work values")
            require(
                all(isinstance(value, str) and value.strip() for value in values),
                f"{programme_id}/{winner['nominationId']}: invalid work value",
            )
            selected += 1
            work_references += len(values)
        selected_by_programme[programme_id] = selected
        selected_results += selected

    require(len(all_ids) == 75, f"expected 75 stable category IDs, found {len(all_ids)}")
    require(len(source_mapping) == 194, f"expected 194 included source labels, found {len(source_mapping)}")
    print(
        "BAFTA category definitions are valid: "
        f"{len(all_ids)} categories, {len(source_mapping)} included source labels, "
        f"{selected_results} selected winner records, {work_references} work references "
        f"({selected_by_programme['film']} Film, {selected_by_programme['television']} Television, "
        f"{selected_by_programme['television-craft']} Television Craft)."
    )


if __name__ == "__main__":
    main()
