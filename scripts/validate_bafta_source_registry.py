#!/usr/bin/env python3
"""Validate the reviewed BAFTA current-category source registry."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "sources" / "bafta" / "current-category-pages.json"

EXPECTED_PROGRAMMES = {
    "film": {
        "name": "BAFTA Film Awards",
        "searchType": "Film",
        "official": 28,
        "included": 25,
        "excluded": 3,
        "annualPath": "/awards/film/",
        "categoryPrefix": "/awards/film/",
    },
    "television": {
        "name": "BAFTA Television Awards",
        "searchType": "Television",
        "official": 29,
        "included": 27,
        "excluded": 2,
        "annualPath": "/awards/television/",
        "categoryPrefix": "/awards/television/",
    },
    "television-craft": {
        "name": "BAFTA Television Craft Awards",
        "searchType": "TV Craft",
        "official": 24,
        "included": 23,
        "excluded": 1,
        "annualPath": "/awards/tv-craft/",
        "categoryPrefix": "/awards/tvcraft/",
    },
}

EXPECTED_SUMMARY = {
    "official2026CategoryCount": 81,
    "includedCurrentCategoryCount": 75,
    "excludedCurrentCategoryCount": 6,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_bafta_url(value: object, label: str, expected_path: str | None = None) -> str:
    require(isinstance(value, str) and value, f"{label} must be a non-empty URL")
    parsed = urlparse(value)
    require(parsed.scheme == "https", f"{label} must use https: {value}")
    require(parsed.netloc == "www.bafta.org", f"{label} must use www.bafta.org: {value}")
    require(not parsed.query and not parsed.fragment, f"{label} must not contain a query or fragment: {value}")
    require(parsed.path.endswith("/"), f"{label} must have a trailing slash: {value}")
    if expected_path is not None:
        require(parsed.path == expected_path, f"{label} must be {expected_path}: {value}")
    return parsed.path


def main() -> None:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    require(payload.get("schemaVersion") == 1, "schemaVersion must be 1")

    checked_at = payload.get("checkedAt")
    require(isinstance(checked_at, str), "checkedAt must be an ISO date")
    try:
        date.fromisoformat(checked_at)
    except ValueError as exc:
        raise ValueError("checkedAt must be an ISO date") from exc

    authority = payload.get("authority")
    require(isinstance(authority, dict), "authority must be an object")
    require(authority.get("name") == "British Academy of Film and Television Arts", "unexpected authority name")
    validate_bafta_url(authority.get("searchPage"), "authority.searchPage", "/awards/search/")

    programmes = payload.get("programmes")
    require(isinstance(programmes, list), "programmes must be an array")
    require(len(programmes) == len(EXPECTED_PROGRAMMES), "registry must contain exactly three programmes")

    programme_ids: set[str] = set()
    category_keys: set[tuple[str, str]] = set()
    history_pages: set[str] = set()
    actual_summary = {
        "official2026CategoryCount": 0,
        "includedCurrentCategoryCount": 0,
        "excludedCurrentCategoryCount": 0,
    }

    for programme in programmes:
        require(isinstance(programme, dict), "each programme must be an object")
        programme_id = programme.get("id")
        require(programme_id in EXPECTED_PROGRAMMES, f"unexpected programme id: {programme_id!r}")
        require(programme_id not in programme_ids, f"duplicate programme id: {programme_id}")
        programme_ids.add(programme_id)
        expected = EXPECTED_PROGRAMMES[programme_id]

        require(programme.get("name") == expected["name"], f"unexpected name for {programme_id}")
        require(programme.get("searchType") == expected["searchType"], f"unexpected searchType for {programme_id}")
        require(
            programme.get("official2026CategoryCount") == expected["official"],
            f"unexpected official 2026 category count for {programme_id}",
        )
        validate_bafta_url(
            programme.get("annualResultsPage"),
            f"{programme_id}.annualResultsPage",
            expected["annualPath"],
        )

        included = programme.get("included")
        excluded = programme.get("excluded")
        require(isinstance(included, list), f"{programme_id}.included must be an array")
        require(isinstance(excluded, list), f"{programme_id}.excluded must be an array")
        require(len(included) == expected["included"], f"unexpected included count for {programme_id}")
        require(len(excluded) == expected["excluded"], f"unexpected excluded count for {programme_id}")
        require(
            len(included) + len(excluded) == programme["official2026CategoryCount"],
            f"included and excluded categories do not reconcile for {programme_id}",
        )

        for category in included:
            require(isinstance(category, dict), f"{programme_id} included category must be an object")
            name = category.get("name")
            require(isinstance(name, str) and name.strip() == name and name, f"invalid included name in {programme_id}")
            key = (programme_id, name.casefold())
            require(key not in category_keys, f"duplicate category name in {programme_id}: {name}")
            category_keys.add(key)

            page = category.get("historyPage")
            path = validate_bafta_url(page, f"{programme_id}.{name}.historyPage")
            require(path.startswith(expected["categoryPrefix"]), f"wrong category-page namespace for {programme_id}: {page}")
            require(path != expected["annualPath"], f"category page cannot be the annual results page: {page}")
            require(page not in history_pages, f"duplicate history page: {page}")
            history_pages.add(page)

        for category in excluded:
            require(isinstance(category, dict), f"{programme_id} excluded category must be an object")
            name = category.get("name")
            reason = category.get("reason")
            require(isinstance(name, str) and name.strip() == name and name, f"invalid excluded name in {programme_id}")
            require(isinstance(reason, str) and reason.strip() == reason and reason, f"missing exclusion reason for {programme_id}: {name}")
            key = (programme_id, name.casefold())
            require(key not in category_keys, f"duplicate category name in {programme_id}: {name}")
            category_keys.add(key)

        actual_summary["official2026CategoryCount"] += programme["official2026CategoryCount"]
        actual_summary["includedCurrentCategoryCount"] += len(included)
        actual_summary["excludedCurrentCategoryCount"] += len(excluded)

    require(programme_ids == set(EXPECTED_PROGRAMMES), "programme set does not match the expected BAFTA scope")
    require(actual_summary == EXPECTED_SUMMARY, f"derived summary does not match the contract: {actual_summary}")
    require(payload.get("summary") == EXPECTED_SUMMARY, "declared summary does not match the contract")

    print(
        "BAFTA source registry is valid: "
        f"{actual_summary['official2026CategoryCount']} official 2026 categories, "
        f"{actual_summary['includedCurrentCategoryCount']} included current pages, "
        f"{actual_summary['excludedCurrentCategoryCount']} explicit exclusions across "
        f"{len(programmes)} programmes."
    )


if __name__ == "__main__":
    main()
