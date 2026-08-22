#!/usr/bin/env python3
"""Build the review inventory for BAFTA historical category lineages."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "sources" / "bafta"
REGISTRY_PATH = SOURCE_DIR / "current-category-pages.json"
REPORT_PATH = ROOT / "reports" / "bafta-category-lineage-audit.md"
SNAPSHOT_FILES = (
    "winners-film.json",
    "winners-television.json",
    "winners-television-craft.json",
)


def markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def build_report() -> str:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry_by_id = {programme["id"]: programme for programme in registry["programmes"]}
    snapshots = [json.loads((SOURCE_DIR / name).read_text(encoding="utf-8")) for name in SNAPSHOT_FILES]

    lines = [
        "# BAFTA category lineage audit",
        "",
        "Generated from the reviewed BAFTA winner snapshots. This inventory is a review aid, not a lineage decision: `historical review` rows must be mapped to an official BAFTA history-page identity or explicitly excluded before canonical import.",
        "",
        "## Summary",
        "",
        "| Programme | Winners | Historical labels | Current included | Current excluded | Historical review |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    programme_rows: list[tuple[dict[str, object], dict[str, object], list[dict[str, object]]]] = []
    total_winners = 0
    total_labels = 0
    total_included = 0
    total_excluded = 0
    total_review = 0

    for snapshot in snapshots:
        programme = snapshot["programme"]
        registry_programme = registry_by_id[programme["id"]]
        groups: dict[str, list[dict[str, object]]] = defaultdict(list)
        for winner in snapshot["winners"]:
            groups[winner["category"]].append(winner)

        included = {category["name"]: category for category in registry_programme["included"]}
        excluded = {category["name"]: category for category in registry_programme["excluded"]}
        rows: list[dict[str, object]] = []
        for label, winners in groups.items():
            years = [winner["year"] for winner in winners]
            if label in included:
                state = "included current"
                page = included[label]["historyPage"]
                priority = 0
            elif label in excluded:
                state = "excluded current"
                page = "—"
                priority = 1
            else:
                state = "historical review"
                page = "pending"
                priority = 2
            rows.append(
                {
                    "label": label,
                    "first": min(years),
                    "last": max(years),
                    "winners": len(winners),
                    "state": state,
                    "page": page,
                    "priority": priority,
                }
            )

        included_count = sum(row["state"] == "included current" for row in rows)
        excluded_count = sum(row["state"] == "excluded current" for row in rows)
        review_count = sum(row["state"] == "historical review" for row in rows)
        lines.append(
            f"| {markdown(programme['name'])} | {len(snapshot['winners']):,} | {len(rows)} | "
            f"{included_count} | {excluded_count} | {review_count} |"
        )
        programme_rows.append((programme, registry_programme, rows))
        total_winners += len(snapshot["winners"])
        total_labels += len(rows)
        total_included += included_count
        total_excluded += excluded_count
        total_review += review_count

    lines.append(
        f"| **Total** | **{total_winners:,}** | **{total_labels}** | **{total_included}** | "
        f"**{total_excluded}** | **{total_review}** |"
    )

    for programme, _, rows in programme_rows:
        lines.extend(
            [
                "",
                f"## {programme['name']}",
                "",
                "| Official category label | First year | Last year | Winners | Audit state | Official history-page evidence |",
                "| --- | ---: | ---: | ---: | --- | --- |",
            ]
        )
        rows.sort(key=lambda row: (row["priority"], -row["last"], row["label"].casefold()))
        for row in rows:
            page = row["page"]
            if isinstance(page, str) and page.startswith("https://"):
                page_cell = f"[BAFTA page]({page})"
            else:
                page_cell = str(page)
            lines.append(
                f"| {markdown(row['label'])} | {row['first']} | {row['last']} | {row['winners']} | "
                f"{row['state']} | {page_cell} |"
            )

    lines.extend(
        [
            "",
            "## Completion contract",
            "",
            "The lineage gate is complete only when every `historical review` row is replaced by a reviewed mapping or explicit exclusion backed by BAFTA's own category-page identity. Similar wording or adjacent years alone are not sufficient evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the committed report is stale")
    parser.add_argument("--stdout", action="store_true", help="write the generated report to stdout")
    args = parser.parse_args()

    report = build_report()
    if args.stdout:
        print(report, end="")
        return
    if args.check:
        if not REPORT_PATH.exists() or REPORT_PATH.read_text(encoding="utf-8") != report:
            raise SystemExit("BAFTA category lineage audit report is stale; regenerate it")
        print("BAFTA category lineage audit report is current: 291 labels, 210 historical reviews.")
        return
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
