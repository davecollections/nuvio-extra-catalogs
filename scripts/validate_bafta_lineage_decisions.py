#!/usr/bin/env python3
"""Validate reviewed BAFTA historical category-lineage decisions."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "sources" / "bafta"
DECISIONS_PATH = SOURCE_DIR / "lineage-decisions.json"
EVIDENCE_PATH = SOURCE_DIR / "category-page-evidence.json"
REGISTRY_PATH = SOURCE_DIR / "current-category-pages.json"
EXPECTED_PROGRAMMES = ("film", "television", "television-craft")
DISPOSITIONS = {"current-lineage", "excluded"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--complete",
        action="store_true",
        help="require a final decision for every historical BAFTA category page",
    )
    args = parser.parse_args()

    decisions = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    evidence_by_id = {programme["id"]: programme for programme in evidence["programmes"]}
    registry_by_id = {programme["id"]: programme for programme in registry["programmes"]}

    require(decisions.get("schemaVersion") == 1, "lineage decisions schemaVersion must be 1")
    checked_at = decisions.get("checkedAt")
    require(isinstance(checked_at, str), "lineage decisions checkedAt must be an ISO date")
    try:
        date.fromisoformat(checked_at)
    except ValueError as exc:
        raise ValueError("lineage decisions checkedAt must be an ISO date") from exc
    require(checked_at >= evidence["checkedAt"], "lineage decisions predate category-page evidence")
    require(
        isinstance(decisions.get("policy"), str) and decisions["policy"].strip(),
        "lineage decisions policy is required",
    )

    programmes = decisions.get("programmes")
    require(isinstance(programmes, list), "lineage decisions programmes must be an array")
    require(
        [programme.get("id") for programme in programmes] == list(EXPECTED_PROGRAMMES),
        "lineage decisions programmes must use the expected deterministic order",
    )

    totals = {disposition: 0 for disposition in DISPOSITIONS}
    total_expected = 0
    for programme in programmes:
        programme_id = programme["id"]
        evidence_programme = evidence_by_id[programme_id]
        registry_programme = registry_by_id[programme_id]
        expected_count = evidence_programme["expectedHistoricalLabelCount"]
        require(
            programme.get("expectedHistoricalLabelCount") == expected_count,
            f"{programme_id}: expectedHistoricalLabelCount is stale",
        )

        evidence_entries = {entry["label"]: entry for entry in evidence_programme["labels"]}
        require(
            len(evidence_entries) == expected_count
            and all(entry["status"] == "resolved" for entry in evidence_entries.values()),
            f"{programme_id}: category-page evidence must be complete before lineage decisions",
        )
        entries = programme.get("decisions")
        require(isinstance(entries, list), f"{programme_id}: decisions must be an array")
        require(
            [entry.get("label", "").casefold() for entry in entries]
            == sorted(entry.get("label", "").casefold() for entry in entries),
            f"{programme_id}: decisions must be sorted by label",
        )
        seen: set[str] = set()
        for entry in entries:
            require(isinstance(entry, dict), f"{programme_id}: decision must be an object")
            label = entry.get("label")
            disposition = entry.get("disposition")
            require(label in evidence_entries, f"{programme_id}: unknown historical label {label!r}")
            require(label not in seen, f"{programme_id}: duplicate lineage decision for {label}")
            require(disposition in DISPOSITIONS, f"{programme_id}: invalid disposition for {label}")
            require(
                entry.get("historyPage") == evidence_entries[label]["historyPage"],
                f"{programme_id}: {label} historyPage differs from reviewed evidence",
            )

            if disposition == "current-lineage":
                target = entry.get("currentCategory")
                target_programme_id = entry.get("currentProgramme", programme_id)
                require(
                    target_programme_id in registry_by_id,
                    f"{programme_id}: {label} maps to unknown current programme {target_programme_id!r}",
                )
                if "currentProgramme" in entry:
                    require(
                        target_programme_id != programme_id,
                        f"{programme_id}: {label} must omit redundant currentProgramme",
                    )
                current_included = {
                    item["name"] for item in registry_by_id[target_programme_id]["included"]
                }
                require(
                    target in current_included,
                    f"{programme_id}: {label} maps to unknown current included category "
                    f"{target_programme_id}/{target!r}",
                )
                require("reason" not in entry, f"{programme_id}: mapped {label} must not have an exclusion reason")
            else:
                reason = entry.get("reason")
                require(
                    isinstance(reason, str) and reason.strip() == reason and reason,
                    f"{programme_id}: excluded {label} requires a reason",
                )
                require("currentCategory" not in entry, f"{programme_id}: excluded {label} cannot map to a current category")
                require("currentProgramme" not in entry, f"{programme_id}: excluded {label} cannot map to a current programme")

            extra = set(entry) - {
                "label",
                "historyPage",
                "disposition",
                "currentCategory",
                "currentProgramme",
                "reason",
                "notes",
            }
            require(not extra, f"{programme_id}: {label} has unsupported keys: {sorted(extra)}")
            if "notes" in entry:
                require(
                    isinstance(entry["notes"], str) and entry["notes"].strip() == entry["notes"] and entry["notes"],
                    f"{programme_id}: {label} notes must be non-empty",
                )

            seen.add(label)
            totals[disposition] += 1

        total_expected += expected_count

    reviewed = sum(totals.values())
    remaining = total_expected - reviewed
    require(remaining >= 0, "lineage decisions exceed the historical evidence inventory")
    if args.complete:
        require(remaining == 0, f"{remaining} historical BAFTA lineage decisions remain")
    print(
        "BAFTA lineage decisions are valid: "
        f"{reviewed}/{total_expected} historical pages decided "
        f"({totals['current-lineage']} current mappings, {totals['excluded']} excluded, "
        f"{remaining} remaining)."
    )


if __name__ == "__main__":
    main()
