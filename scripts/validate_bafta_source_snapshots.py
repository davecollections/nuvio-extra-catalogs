#!/usr/bin/env python3
"""Validate the reviewed, winner-only BAFTA annual source snapshots."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "sources" / "bafta"
REGISTRY_PATH = SOURCE_DIR / "current-category-pages.json"

EXPECTED_YEARS = list(range(2026, 1948, -1))
EXPECTED_AUTHORITY = {
    "name": "British Academy of Film and Television Arts",
    "searchPage": "https://www.bafta.org/awards/search/",
}
EXPECTED_PROGRAMMES = {
    "film": {
        "file": "winners-film.json",
        "name": "BAFTA Film Awards",
        "label": "Film",
        "annualResultsPage": "https://www.bafta.org/awards/film/",
        "winnerCount": 1634,
        "categoryLabelCount": 89,
        "zeroYears": [],
    },
    "television": {
        "file": "winners-television.json",
        "name": "BAFTA Television Awards",
        "label": "Television",
        "annualResultsPage": "https://www.bafta.org/awards/television/",
        "winnerCount": 1520,
        "categoryLabelCount": 124,
        "zeroYears": [1968, 1953, 1952, 1951, 1950, 1949],
    },
    "television-craft": {
        "file": "winners-television-craft.json",
        "name": "BAFTA Television Craft Awards",
        "label": "TV Craft",
        "annualResultsPage": "https://www.bafta.org/awards/tv-craft/",
        "winnerCount": 757,
        "categoryLabelCount": 78,
        "zeroYears": list(range(1977, 1948, -1)),
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_url(value: object, label: str, expected: str | None = None) -> str:
    require(isinstance(value, str) and value, f"{label} must be a non-empty URL")
    parsed = urlparse(value)
    require(parsed.scheme == "https", f"{label} must use https: {value}")
    require(parsed.netloc == "www.bafta.org", f"{label} must use www.bafta.org: {value}")
    require(not parsed.fragment, f"{label} must not contain a fragment: {value}")
    if expected is not None:
        require(value == expected, f"{label} must be {expected}: {value}")
    return value


def main() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry_programmes = {programme["id"]: programme for programme in registry["programmes"]}
    require(set(registry_programmes) == set(EXPECTED_PROGRAMMES), "registry programme set is unexpected")

    global_ids: set[str] = set()
    total_winners = 0
    total_labels = 0

    for programme_id, expected in EXPECTED_PROGRAMMES.items():
        path = SOURCE_DIR / expected["file"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        require(payload.get("schemaVersion") == 1, f"{path.name}: schemaVersion must be 1")
        require(payload.get("checkedAt") == registry["checkedAt"], f"{path.name}: checkedAt must match the registry")
        require(payload.get("authority") == EXPECTED_AUTHORITY, f"{path.name}: authority is unexpected")

        programme = payload.get("programme")
        require(isinstance(programme, dict), f"{path.name}: programme must be an object")
        require(programme.get("id") == programme_id, f"{path.name}: unexpected programme id")
        for field in ("name", "label", "annualResultsPage"):
            require(programme.get(field) == expected[field], f"{path.name}: unexpected programme {field}")
        validate_url(programme["annualResultsPage"], f"{path.name}: annualResultsPage", expected["annualResultsPage"])

        pages = payload.get("resultsPages")
        winners = payload.get("winners")
        require(isinstance(pages, list), f"{path.name}: resultsPages must be an array")
        require(isinstance(winners, list), f"{path.name}: winners must be an array")
        require([page.get("year") for page in pages] == EXPECTED_YEARS, f"{path.name}: result years must be 2026–1949 descending")
        require(len(winners) == expected["winnerCount"], f"{path.name}: unexpected winner count")

        page_by_year: dict[int, dict[str, object]] = {}
        for page in pages:
            require(isinstance(page, dict), f"{path.name}: result page entry must be an object")
            year = page.get("year")
            require(isinstance(year, int), f"{path.name}: result page year must be an integer")
            expected_url = f"{expected['annualResultsPage']}?award-year={year}"
            validate_url(page.get("sourceUrl"), f"{path.name}: {year} sourceUrl", expected_url)
            require(page.get("resultsPage") is True, f"{path.name}: {year} must retain its official results heading")
            nomination_count = page.get("nominationCount")
            winner_count = page.get("winnerCount")
            require(isinstance(nomination_count, int) and nomination_count >= 0, f"{path.name}: invalid {year} nomination count")
            require(isinstance(winner_count, int) and winner_count >= 0, f"{path.name}: invalid {year} winner count")
            require(nomination_count >= winner_count, f"{path.name}: {year} has more winners than nominations")
            page_by_year[year] = page

        zero_years = [year for year in EXPECTED_YEARS if page_by_year[year]["winnerCount"] == 0]
        require(zero_years == expected["zeroYears"], f"{path.name}: unexpected zero-result years: {zero_years}")
        require(sum(page["winnerCount"] for page in pages) == len(winners), f"{path.name}: annual winner counts do not reconcile")

        ids: set[str] = set()
        counts_by_year: Counter[int] = Counter()
        ordering: list[tuple[int, int]] = []
        category_labels: set[str] = set()
        for index, winner in enumerate(winners):
            require(isinstance(winner, dict), f"{path.name}: winner {index} must be an object")
            nomination_id = winner.get("nominationId")
            year = winner.get("year")
            category = winner.get("category")
            heading = winner.get("heading")
            details = winner.get("details")
            require(isinstance(nomination_id, str) and nomination_id.isdigit(), f"{path.name}: invalid nomination ID at winner {index}")
            require(nomination_id not in ids, f"{path.name}: duplicate nomination ID {nomination_id}")
            require(nomination_id not in global_ids, f"global duplicate BAFTA nomination ID {nomination_id}")
            require(year in page_by_year, f"{path.name}: winner {nomination_id} has an invalid year")
            require(winner.get("status") == "Winner", f"{path.name}: {nomination_id} is not marked Winner")
            require(isinstance(category, str) and category.strip() == category and category, f"{path.name}: invalid category for {nomination_id}")
            require(isinstance(heading, str) and heading.strip() == heading and heading, f"{path.name}: invalid heading for {nomination_id}")
            require(isinstance(details, list), f"{path.name}: details must be an array for {nomination_id}")
            require(all(isinstance(value, str) and value.strip() == value and value for value in details), f"{path.name}: invalid detail for {nomination_id}")
            ids.add(nomination_id)
            global_ids.add(nomination_id)
            counts_by_year[year] += 1
            category_labels.add(category)
            ordering.append((-year, int(nomination_id)))

        require(ordering == sorted(ordering), f"{path.name}: winners are not deterministically ordered")
        for year, page in page_by_year.items():
            require(counts_by_year[year] == page["winnerCount"], f"{path.name}: {year} winner records do not match its page count")
        require(len(category_labels) == expected["categoryLabelCount"], f"{path.name}: unexpected historical category-label count")

        current_categories = {winner["category"] for winner in winners if winner["year"] == 2026}
        registry_categories = {
            category["name"]
            for group in (registry_programmes[programme_id]["included"], registry_programmes[programme_id]["excluded"])
            for category in group
        }
        require(current_categories == registry_categories, f"{path.name}: 2026 categories do not exactly match the current-page registry")

        total_winners += len(winners)
        total_labels += len(category_labels)

    require(total_winners == 3911, "unexpected total BAFTA winner count")
    require(len(global_ids) == total_winners, "BAFTA nomination IDs are not globally unique")
    require(total_labels == 291, "unexpected total BAFTA historical category-label count")

    print(
        "BAFTA source snapshots are valid: "
        f"{len(EXPECTED_PROGRAMMES)} programmes, {len(EXPECTED_YEARS)} result years each, "
        f"{total_winners} winners, {total_labels} historical category labels, "
        f"{len(global_ids)} unique nomination IDs."
    )


if __name__ == "__main__":
    main()
