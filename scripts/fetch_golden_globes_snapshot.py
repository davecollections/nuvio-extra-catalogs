#!/usr/bin/env python3
"""Fetch a reviewable winner-only snapshot from the official Golden Globes archive."""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = (
    REPO_ROOT
    / "data"
    / "sources"
    / "golden-globes"
    / "official-winners-1944-2026.json"
)
SOURCE_REFERENCE = "https://goldenglobes.com/winners-nominees/"
FILTERS_ENDPOINT = (
    "https://goldenglobes.com/wp-json/awdb/v1/winners-and-nominees/filters/"
)
YEAR_ENDPOINT = (
    "https://goldenglobes.com/wp-json/awdb/v1/winners-and-nominees/?year={year}"
)
EXPECTED_YEARS = list(range(2026, 1943, -1))


class SnapshotError(RuntimeError):
    pass


def fetch_json(url: str) -> object:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "nuvio-extra-catalogs-reviewed-maintenance/1.0",
        },
    )
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))
    raise SnapshotError(f"could not fetch {url}: {last_error}")


def clean_item(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise SnapshotError("official recipient item must be an object")
    item = {
        "officialId": raw.get("id"),
        "type": raw.get("type"),
        "title": raw.get("title"),
    }
    if raw.get("link"):
        item["link"] = raw["link"]
    if raw.get("countries"):
        item["countries"] = raw["countries"]
    if not isinstance(item["officialId"], int) or item["officialId"] < 1:
        raise SnapshotError(f"official item has invalid ID: {raw!r}")
    if not isinstance(item["type"], str) or not item["type"].strip():
        raise SnapshotError(f"official item has invalid type: {raw!r}")
    if not isinstance(item["title"], str) or not item["title"].strip():
        raise SnapshotError(f"official item has invalid title: {raw!r}")
    return item


def clean_winner(raw: object, expected_year: int) -> dict:
    if not isinstance(raw, dict):
        raise SnapshotError("official nomination must be an object")
    if raw.get("winner") is not True:
        raise SnapshotError("snapshot attempted to retain a non-winner nomination")
    if str(raw.get("year")) != str(expected_year):
        raise SnapshotError(f"official nomination year does not match {expected_year}")
    recipients = raw.get("nominees")
    if not isinstance(recipients, list):
        raise SnapshotError("official winner nomination has an invalid recipient array")
    winner = {
        "officialId": raw.get("id"),
        "nomineeType": raw.get("nominee_type"),
        "recipients": [clean_item(item) for item in recipients],
    }
    if not isinstance(winner["officialId"], int) or winner["officialId"] < 1:
        raise SnapshotError("official winner nomination has an invalid ID")
    if not isinstance(winner["nomineeType"], str) or not winner["nomineeType"].strip():
        raise SnapshotError("official winner nomination has an invalid nominee type")
    if raw.get("show") is not None:
        winner["show"] = clean_item(raw["show"])
    return winner


def build_snapshot(checked_at: str) -> dict:
    filters = fetch_json(FILTERS_ENDPOINT)
    if not isinstance(filters, dict) or filters.get("years") != EXPECTED_YEARS:
        raise SnapshotError(
            "official year coverage changed; review the new ceremony before updating the snapshot"
        )

    years: list[dict] = []
    winner_count = 0
    for year in EXPECTED_YEARS:
        raw_groups = fetch_json(YEAR_ENDPOINT.format(year=year))
        if not isinstance(raw_groups, list) or not raw_groups:
            raise SnapshotError(f"official archive returned no groups for {year}")
        groups: list[dict] = []
        for raw_group in raw_groups:
            if not isinstance(raw_group, dict):
                raise SnapshotError(f"official group for {year} must be an object")
            award = raw_group.get("award")
            order = raw_group.get("order")
            nominations = raw_group.get("nominations")
            if not isinstance(award, str) or not award.strip():
                raise SnapshotError(f"official group for {year} has an invalid award label")
            if not isinstance(order, int):
                raise SnapshotError(f"official group {award!r} has an invalid order")
            if not isinstance(nominations, list):
                raise SnapshotError(f"official group {award!r} has invalid nominations")
            winners = [
                clean_winner(item, year)
                for item in nominations
                if isinstance(item, dict) and item.get("winner") is True
            ]
            if not winners:
                continue
            winner_count += len(winners)
            groups.append(
                {
                    "officialCategory": award.strip(),
                    "officialOrder": order,
                    "winners": winners,
                }
            )
        years.append(
            {
                "year": year,
                "ceremonyNumber": year - 1943,
                "groups": groups,
            }
        )

    if winner_count != 2029:
        raise SnapshotError(
            f"expected 2,029 official winner records, found {winner_count}; review source drift"
        )
    return {
        "schemaVersion": 1,
        "source": {
            "name": "Golden Globes Winners & Nominees Database",
            "reference": SOURCE_REFERENCE,
            "filtersEndpoint": FILTERS_ENDPOINT,
            "yearEndpointTemplate": YEAR_ENDPOINT,
            "checkedAt": checked_at,
        },
        "coverage": {
            "firstYear": 1944,
            "lastYear": 2026,
            "firstCeremonyNumber": 1,
            "lastCeremonyNumber": 83,
        },
        "winnerRecordCount": winner_count,
        "years": years,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checked-at", default=date.today().isoformat())
    args = parser.parse_args()
    try:
        date.fromisoformat(args.checked_at)
        snapshot = build_snapshot(args.checked_at)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"Wrote {OUTPUT_PATH} with {snapshot['winnerRecordCount']} winner records "
            f"across {len(snapshot['years'])} ceremonies."
        )
        return 0
    except (SnapshotError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
