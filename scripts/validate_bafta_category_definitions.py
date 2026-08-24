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
        {
            "schemaVersion",
            "awardBodyId",
            "programmes",
            "sourceOverrides",
            "workSplits",
            "workOmissions",
        },
        {
            "schemaVersion",
            "awardBodyId",
            "programmes",
            "sourceOverrides",
            "workSplits",
            "workOmissions",
        },
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
            expected_media_type = (
                "movie"
                if programme_id == "film"
                and category_id
                not in {"film-british-short-animation", "film-documentary"}
                else "mixed"
            )
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
        [
            (
                entry.get("programme"),
                entry.get("label", "").casefold(),
                int(entry.get("nominationId", "0")),
            )
            for entry in overrides
        ]
        == sorted(
            (
                entry.get("programme"),
                entry.get("label", "").casefold(),
                int(entry.get("nominationId", "0")),
            )
            for entry in overrides
        ),
        "sourceOverrides must be sorted by programme, label, and nominationId",
    )
    snapshot_winners = {
        (programme_id, winner["nominationId"]): winner
        for programme_id, snapshot_path in SNAPSHOTS.items()
        for winner in load_json(snapshot_path)["winners"]
    }
    override_fields: dict[tuple[str, str, str | None], str] = {}
    for entry in overrides:
        exact_keys(
            entry,
            {"programme", "label", "workField"},
            {"programme", "label", "nominationId", "workField"},
            "source override",
        )
        source_key = (entry["programme"], entry["label"])
        require(source_key in source_mapping, f"source override has no included mapping: {source_key}")
        nomination_id = entry.get("nominationId")
        if nomination_id is not None:
            require(
                isinstance(nomination_id, str) and nomination_id.isdigit(),
                f"source override has invalid nominationId: {source_key}",
            )
            winner = snapshot_winners.get((entry["programme"], nomination_id))
            require(winner is not None, f"source override has unknown nominationId: {source_key}")
            require(
                winner["category"] == entry["label"],
                f"source override nominationId belongs to another label: {source_key}",
            )
        key = (entry["programme"], entry["label"], nomination_id)
        require(key not in override_fields, f"duplicate source override: {key}")
        require(entry["workField"] in WORK_FIELDS, f"source override has invalid workField: {key}")
        inherited = override_fields.get(
            (entry["programme"], entry["label"], None),
            source_mapping[source_key]["workField"],
        )
        require(
            entry["workField"] != inherited,
            f"source override is redundant: {key}",
        )
        override_fields[key] = entry["workField"]

    work_splits = definitions["workSplits"]
    require(isinstance(work_splits, list), "workSplits must be an array")
    programme_order = {programme_id: index for index, programme_id in enumerate(EXPECTED_PROGRAMMES)}
    require(
        [
            (programme_order.get(entry.get("programme"), 99), int(entry.get("nominationId", "0")))
            for entry in work_splits
        ]
        == sorted(
            (programme_order.get(entry.get("programme"), 99), int(entry.get("nominationId", "0")))
            for entry in work_splits
        ),
        "workSplits must be sorted by programme and nominationId",
    )
    split_values: dict[tuple[str, str], list[str]] = {}
    for entry in work_splits:
        exact_keys(
            entry,
            {"programme", "nominationId", "sourceValue", "values", "reason"},
            {"programme", "nominationId", "sourceValue", "values", "reason"},
            "work split",
        )
        programme_id = entry["programme"]
        nomination_id = entry["nominationId"]
        require(programme_id in EXPECTED_PROGRAMMES, "work split has unknown programme")
        require(
            isinstance(nomination_id, str) and nomination_id.isdigit(),
            "work split has invalid nominationId",
        )
        key = (programme_id, nomination_id)
        require(key not in split_values, f"duplicate work split: {key}")
        winner = snapshot_winners.get(key)
        require(winner is not None, f"work split has unknown nominationId: {key}")
        category = source_mapping.get((programme_id, winner["category"]))
        require(category is not None, f"work split is not in an included lineage: {key}")
        field = override_fields.get(
            (programme_id, winner["category"], nomination_id),
            override_fields.get(
                (programme_id, winner["category"], None), category["workField"]
            ),
        )
        raw_values = [winner["heading"]] if field == "heading" else winner["details"]
        require(
            raw_values == [entry["sourceValue"]],
            f"work split source value does not match the official snapshot: {key}",
        )
        values = entry["values"]
        require(
            isinstance(values, list)
            and len(values) >= 2
            and all(isinstance(value, str) and value.strip() == value for value in values),
            f"work split requires at least two exact values: {key}",
        )
        require(
            "/".join(values) == entry["sourceValue"],
            f"work split values do not reconstruct the official source value: {key}",
        )
        require(
            isinstance(entry["reason"], str) and entry["reason"].strip() == entry["reason"],
            f"work split requires a reason: {key}",
        )
        split_values[key] = values

    omissions = definitions["workOmissions"]
    require(isinstance(omissions, list), "workOmissions must be an array")
    require(
        [(programme_order.get(entry.get("programme"), 99), int(entry.get("nominationId", "0"))) for entry in omissions]
        == sorted(
            (programme_order.get(entry.get("programme"), 99), int(entry.get("nominationId", "0")))
            for entry in omissions
        ),
        "workOmissions must be sorted by programme and nominationId",
    )
    omission_keys: set[tuple[str, str]] = set()
    for entry in omissions:
        exact_keys(
            entry,
            {"programme", "nominationId", "reason"},
            {"programme", "nominationId", "reason"},
            "work omission",
        )
        programme_id = entry["programme"]
        nomination_id = entry["nominationId"]
        require(programme_id in EXPECTED_PROGRAMMES, "work omission has unknown programme")
        require(isinstance(nomination_id, str) and nomination_id.isdigit(), "work omission has invalid nominationId")
        require(isinstance(entry["reason"], str) and entry["reason"].strip() == entry["reason"], "work omission requires a reason")
        key = (programme_id, nomination_id)
        require(key not in omission_keys, f"duplicate work omission: {key}")
        omission_keys.add(key)

    selected_results = 0
    work_references = 0
    selected_by_programme: dict[str, int] = {}
    seen_omissions: set[tuple[str, str]] = set()
    for programme_id, snapshot_path in SNAPSHOTS.items():
        snapshot = load_json(snapshot_path)
        selected = 0
        for winner in snapshot["winners"]:
            key = (programme_id, winner["category"])
            category = source_mapping.get(key)
            if category is None:
                continue
            field = override_fields.get(
                (programme_id, winner["category"], winner["nominationId"]),
                override_fields.get((programme_id, winner["category"], None), category["workField"]),
            )
            if field == "heading":
                values = [winner.get("heading")]
            else:
                values = winner.get("details")
            require(isinstance(values, list) and values, f"{programme_id}/{winner['nominationId']}: no work values")
            require(
                all(isinstance(value, str) and value.strip() for value in values),
                f"{programme_id}/{winner['nominationId']}: invalid work value",
            )
            normalized_heading = re.sub(r"[^a-z0-9]+", "", winner["heading"].casefold())
            repeats_source_text = bool(winner.get("details")) and all(
                re.sub(r"[^a-z0-9]+", "", value.casefold()) == normalized_heading
                for value in winner["details"]
            )
            omission_key = (programme_id, winner["nominationId"])
            if omission_key in omission_keys:
                require(
                    repeats_source_text,
                    f"{programme_id}/{winner['nominationId']}: work omission is no longer justified",
                )
                seen_omissions.add(omission_key)
                continue
            require(
                not repeats_source_text,
                f"{programme_id}/{winner['nominationId']}: record repeats the credited name and requires an explicit work omission",
            )
            selected += 1
            work_references += len(split_values.get(omission_key, values))
        selected_by_programme[programme_id] = selected
        selected_results += selected

    require(len(all_ids) == 75, f"expected 75 stable category IDs, found {len(all_ids)}")
    require(len(source_mapping) == 194, f"expected 194 included source labels, found {len(source_mapping)}")
    require(seen_omissions == omission_keys, "one or more work omissions do not reference selected winner records")
    require(
        set(split_values).isdisjoint(omission_keys),
        "a work split cannot also be a no-work omission",
    )
    print(
        "BAFTA category definitions are valid: "
        f"{len(all_ids)} categories, {len(source_mapping)} included source labels, "
        f"{selected_results} selected winner records, {work_references} work references, "
        f"{len(work_splits)} explicit multi-work splits, "
        f"{len(omission_keys)} explicit no-work omissions "
        f"({selected_by_programme['film']} Film, {selected_by_programme['television']} Television, "
        f"{selected_by_programme['television-craft']} Television Craft)."
    )


if __name__ == "__main__":
    main()
