"""Shared deterministic BAFTA source-selection helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from enrich_golden_globes_identities import clean_text, normalized_title


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "sources" / "bafta"
DEFINITIONS_PATH = SOURCE_DIR / "category-definitions.json"
DECISIONS_PATH = SOURCE_DIR / "lineage-decisions.json"
SNAPSHOTS = {
    "film": SOURCE_DIR / "winners-film.json",
    "television": SOURCE_DIR / "winners-television.json",
    "television-craft": SOURCE_DIR / "winners-television-craft.json",
}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def load_category_contract() -> tuple[
    dict,
    dict[tuple[str, str], dict],
    dict[tuple[str, str, str | None], str],
    dict[tuple[str, str], list[str]],
    set[tuple[str, str]],
]:
    definitions = load_json(DEFINITIONS_PATH)
    decisions = load_json(DECISIONS_PATH)
    categories_by_programme = {
        programme["id"]: {category["name"]: category for category in programme["categories"]}
        for programme in definitions["programmes"]
    }
    source_mapping: dict[tuple[str, str], dict] = {}
    for programme_id, categories in categories_by_programme.items():
        for name, category in categories.items():
            source_mapping[(programme_id, name)] = category
    for programme in decisions["programmes"]:
        programme_id = programme["id"]
        for decision in programme["decisions"]:
            if decision["disposition"] != "current-lineage":
                continue
            target_programme = decision.get("currentProgramme", programme_id)
            source_mapping[(programme_id, decision["label"])] = categories_by_programme[
                target_programme
            ][decision["currentCategory"]]
    overrides = {
        (entry["programme"], entry["label"], entry.get("nominationId")): entry["workField"]
        for entry in definitions["sourceOverrides"]
    }
    splits = {
        (entry["programme"], entry["nominationId"]): entry["values"]
        for entry in definitions["workSplits"]
    }
    omissions = {
        (entry["programme"], entry["nominationId"])
        for entry in definitions["workOmissions"]
    }
    return definitions, source_mapping, overrides, splits, omissions


def selected_winners() -> Iterator[dict]:
    _, source_mapping, overrides, splits, omissions = load_category_contract()
    for programme_id, snapshot_path in SNAPSHOTS.items():
        snapshot = load_json(snapshot_path)
        for winner in snapshot["winners"]:
            source_key = (programme_id, winner["category"])
            category = source_mapping.get(source_key)
            if category is None or (programme_id, winner["nominationId"]) in omissions:
                continue
            work_field = overrides.get(
                (programme_id, winner["category"], winner["nominationId"]),
                overrides.get((programme_id, winner["category"], None), category["workField"]),
            )
            source_work_values = (
                [winner["heading"]] if work_field == "heading" else winner["details"]
            )
            work_values = splits.get(
                (programme_id, winner["nominationId"]), source_work_values
            )
            if len(source_work_values) != 1 or not work_values:
                raise ValueError(
                    f"{programme_id}/{winner['nominationId']}: expected exactly one work reference"
                )
            recipient_values = winner["details"] if work_field == "heading" else [winner["heading"]]
            for work_value in work_values:
                yield {
                    "programme": programme_id,
                    "category": category,
                    "sourceCategory": winner["category"],
                    "nominationId": winner["nominationId"],
                    "year": winner["year"],
                    "workTitle": clean_text(work_value),
                    "recipientValues": [clean_text(value) for value in recipient_values],
                }


def work_key(entry: dict) -> str:
    title = normalized_title(entry["workTitle"])
    # Film award identities keep their established movie-prefixed audit keys
    # even when a historical lineage is mixed media. The resolved media type,
    # not this inventory key, decides the eventual catalogue route.
    if entry["programme"] == "film":
        return f"movie:{title}:{entry['year']}"
    # BAFTA reuses identical source titles for unrelated television works and
    # adaptations (for example, Bleak House in 1986 and 2006). Keep the award
    # year in the unresolved key so those identities can be reviewed
    # independently. Canonical outputs later deduplicate repeated wins by the
    # resolved IMDb identity, not by title text.
    return f"television:{title}:{entry['year']}"
