#!/usr/bin/env python3
"""Validate incremental first-party BAFTA category history-page evidence."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "sources" / "bafta"
EVIDENCE_PATH = SOURCE_DIR / "category-page-evidence.json"
REGISTRY_PATH = SOURCE_DIR / "current-category-pages.json"
SNAPSHOT_FILES = (
    "winners-film.json",
    "winners-television.json",
    "winners-television-craft.json",
)
EXPECTED_AUTHORITY = {
    "name": "British Academy of Film and Television Arts",
    "searchPage": "https://www.bafta.org/awards/search/",
}
EXPECTED_NAMESPACES = {
    "film": "/awards/film/",
    "television": "/awards/television/",
    "television-craft": "/awards/tvcraft/",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def official_url(value: object, label: str, expected_path: str | None = None) -> str:
    require(isinstance(value, str) and value, f"{label} must be a non-empty URL")
    parsed = urlparse(value)
    require(parsed.scheme == "https", f"{label} must use https: {value}")
    require(parsed.netloc == "www.bafta.org", f"{label} must use www.bafta.org: {value}")
    require(not parsed.fragment, f"{label} must not contain a fragment: {value}")
    if expected_path is not None:
        require(parsed.path.startswith(expected_path), f"{label} has the wrong BAFTA namespace: {value}")
    return value


def main() -> None:
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    snapshots = {
        payload["programme"]["id"]: payload
        for payload in (
            json.loads((SOURCE_DIR / filename).read_text(encoding="utf-8"))
            for filename in SNAPSHOT_FILES
        )
    }
    registry_programmes = {programme["id"]: programme for programme in registry["programmes"]}

    require(evidence.get("schemaVersion") == 1, "category-page evidence schemaVersion must be 1")
    require(evidence.get("checkedAt") >= registry["checkedAt"], "evidence checkedAt predates the source registry")
    require(evidence.get("authority") == EXPECTED_AUTHORITY, "category-page evidence authority is unexpected")
    require(isinstance(evidence.get("method"), str) and evidence["method"], "evidence method is required")

    programmes = evidence.get("programmes")
    require(isinstance(programmes, list), "evidence programmes must be an array")
    require([programme.get("id") for programme in programmes] == list(EXPECTED_NAMESPACES), "evidence programmes must use the expected deterministic order")

    total_expected = 0
    total_resolved = 0
    total_unresolved = 0
    for programme in programmes:
        programme_id = programme["id"]
        snapshot = snapshots[programme_id]
        registry_programme = registry_programmes[programme_id]
        current_labels = {
            category["name"]
            for group in ("included", "excluded")
            for category in registry_programme[group]
        }
        winners_by_id = {winner["nominationId"]: winner for winner in snapshot["winners"]}
        historical_labels = {winner["category"] for winner in snapshot["winners"]} - current_labels
        expected_count = programme.get("expectedHistoricalLabelCount")
        require(expected_count == len(historical_labels), f"{programme_id}: expectedHistoricalLabelCount is stale")

        labels = programme.get("labels")
        require(isinstance(labels, list), f"{programme_id}: labels must be an array")
        require(
            [entry.get("label", "").casefold() for entry in labels]
            == sorted(entry.get("label", "").casefold() for entry in labels),
            f"{programme_id}: evidence labels must be sorted",
        )
        seen: set[str] = set()
        for entry in labels:
            require(isinstance(entry, dict), f"{programme_id}: evidence entry must be an object")
            label = entry.get("label")
            status = entry.get("status")
            nomination_id = entry.get("evidenceNominationId")
            require(isinstance(label, str) and label in historical_labels, f"{programme_id}: unknown historical label {label!r}")
            require(label not in seen, f"{programme_id}: duplicate evidence label {label}")
            require(status in {"resolved", "unresolved"}, f"{programme_id}: invalid status for {label}")
            require(isinstance(nomination_id, str) and nomination_id in winners_by_id, f"{programme_id}: invalid evidence nomination for {label}")
            require(winners_by_id[nomination_id]["category"] == label, f"{programme_id}: nomination {nomination_id} does not evidence {label}")

            search_page = official_url(entry.get("evidenceSearchPage"), f"{programme_id}: {label} evidenceSearchPage")
            parsed_search = urlparse(search_page)
            query = parse_qs(parsed_search.query)
            require(parsed_search.path == "/awards/search/", f"{programme_id}: {label} evidence must use the BAFTA awards search")
            require(query.get("winner") == ["winner"], f"{programme_id}: {label} evidence must be winner-filtered")
            require(query.get("type") == [snapshot["programme"]["label"]], f"{programme_id}: {label} evidence has the wrong programme filter")
            require(bool(query.get("search", [""])[0].strip()), f"{programme_id}: {label} evidence search term is empty")

            if status == "resolved":
                history_page = official_url(entry.get("historyPage"), f"{programme_id}: {label} historyPage", EXPECTED_NAMESPACES[programme_id])
                require(urlparse(history_page).query == "", f"{programme_id}: {label} historyPage must not have a query")
                total_resolved += 1
            else:
                require("historyPage" not in entry, f"{programme_id}: unresolved {label} must not claim a historyPage")
                require(isinstance(entry.get("notes"), str) and entry["notes"], f"{programme_id}: unresolved {label} requires notes")
                total_unresolved += 1

            seen.add(label)

        total_expected += expected_count

    reviewed = total_resolved + total_unresolved
    require(reviewed <= total_expected, "category-page evidence exceeds the historical-label inventory")
    print(
        "BAFTA category-page evidence is valid: "
        f"{reviewed}/{total_expected} historical labels reviewed "
        f"({total_resolved} resolved, {total_unresolved} unresolved, {total_expected - reviewed} remaining)."
    )


if __name__ == "__main__":
    main()
