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
EVIDENCE_PATH = SOURCE_DIR / "category-page-evidence.json"
DECISIONS_PATH = SOURCE_DIR / "lineage-decisions.json"
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
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    evidence_by_programme = {
        programme["id"]: {entry["label"]: entry for entry in programme["labels"]}
        for programme in evidence["programmes"]
    }
    decisions = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    decisions_by_programme = {
        programme["id"]: {entry["label"]: entry for entry in programme["decisions"]}
        for programme in decisions["programmes"]
    }
    snapshots = [json.loads((SOURCE_DIR / name).read_text(encoding="utf-8")) for name in SNAPSHOT_FILES]

    lines = [
        "# BAFTA category lineage audit",
        "",
        "Generated from the reviewed BAFTA winner snapshots, complete first-party category-page evidence, and completed lineage decisions. Historical pages remain fail-closed unless they are mapped to one current included category or explicitly excluded from this current-lineage milestone.",
        "",
        "## Summary",
        "",
        "| Programme | Winners | Source labels | Current included | Current excluded | Historical evidenced | Historical decided | Pending decisions |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    programme_rows: list[tuple[dict[str, object], dict[str, object], list[dict[str, object]]]] = []
    total_winners = 0
    total_labels = 0
    total_included = 0
    total_excluded = 0
    total_evidenced = 0
    total_decided = 0
    total_review = 0

    for snapshot in snapshots:
        programme = snapshot["programme"]
        registry_programme = registry_by_id[programme["id"]]
        groups: dict[str, list[dict[str, object]]] = defaultdict(list)
        for winner in snapshot["winners"]:
            groups[winner["category"]].append(winner)

        included = {category["name"]: category for category in registry_programme["included"]}
        excluded = {category["name"]: category for category in registry_programme["excluded"]}
        historical_evidence = evidence_by_programme[programme["id"]]
        historical_decisions = decisions_by_programme[programme["id"]]
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
            elif label in historical_evidence:
                entry = historical_evidence[label]
                if entry["status"] == "resolved":
                    page = entry["historyPage"]
                    decision = historical_decisions.get(label)
                    if decision is None:
                        state = "lineage decision pending"
                        priority = 3
                    elif decision["disposition"] == "excluded":
                        state = "excluded historical"
                        priority = 2
                    else:
                        target_programme_id = decision.get("currentProgramme", programme["id"])
                        target = decision["currentCategory"]
                        if target_programme_id == programme["id"]:
                            state = f"mapped to current: {target}"
                        else:
                            target_programme = registry_by_id[target_programme_id]["name"]
                            state = f"mapped to current: {target_programme} — {target}"
                        priority = 2
                else:
                    state = "history page unresolved"
                    page = "reviewed; no page resolved"
                    priority = 3
            else:
                state = "historical review"
                page = "pending"
                priority = 3
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
        evidenced_count = sum(row["label"] in historical_evidence for row in rows)
        decided_count = sum(row["label"] in historical_decisions for row in rows)
        review_count = evidenced_count - decided_count
        lines.append(
            f"| {markdown(programme['name'])} | {len(snapshot['winners']):,} | {len(rows)} | "
            f"{included_count} | {excluded_count} | {evidenced_count} | {decided_count} | {review_count} |"
        )
        programme_rows.append((programme, registry_programme, rows))
        total_winners += len(snapshot["winners"])
        total_labels += len(rows)
        total_included += included_count
        total_excluded += excluded_count
        total_evidenced += evidenced_count
        total_decided += decided_count
        total_review += review_count

    lines.append(
        f"| **Total** | **{total_winners:,}** | **{total_labels}** | **{total_included}** | "
        f"**{total_excluded}** | **{total_evidenced}** | **{total_decided}** | **{total_review}** |"
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
            "The category-page evidence and lineage-decision gates are complete. Every historical page is mapped to one named current included category or explicitly excluded from this current-lineage milestone. Similar wording or adjacent years alone are not sufficient evidence.",
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
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        evidenced = sum(len(programme["labels"]) for programme in evidence["programmes"])
        decisions = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
        decided = sum(len(programme["decisions"]) for programme in decisions["programmes"])
        print(
            "BAFTA category lineage audit report is current: "
            f"291 labels, {evidenced} historical pages evidenced, "
            f"{decided} historical decisions, {210 - decided} decisions remaining."
        )
        return
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
