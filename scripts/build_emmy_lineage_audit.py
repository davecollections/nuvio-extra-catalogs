#!/usr/bin/env python3
"""Deterministic source-review report; source acquisition is not acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from fetch_emmy_snapshot import INDEX_PATH, REGISTRY_PATH, SNAPSHOT_PATH, SOURCE_DIR, category_for_year, load, serialized

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "emmy-awards-source-audit.json"


def build():
    paths = [REGISTRY_PATH, INDEX_PATH, SOURCE_DIR / "lineage-decisions.json", SNAPSHOT_PATH,
             SOURCE_DIR / "winner-release-evidence-2026.json"]
    # Match existing awards inventory hashing: canonical JSON avoids Git's
    # platform-specific LF/CRLF checkout conversion changing the audit.
    inputs = {p.name: hashlib.sha256(json.dumps(load(p), ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        for p in [*paths, ROOT / "manifest.json"]}
    registry, index, lineage, snapshot, releases = [load(p) for p in paths]
    decisions = [d for p in lineage["programmes"] for d in p["decisions"]]
    by_slug = {d["sourceSlug"]: d for d in decisions}
    winners = [(p, w) for p in snapshot["pages"] for w in p["winners"]]
    credit_gaps = [{"year": p["year"], "sourceCategory": p["sourceCategory"], "sourceUrl": p["sourceUrl"],
        "sourceKey": w["sourceKey"], "heading": w["heading"],
        "issue": "unavailable-credit-label" if any(c["name"].strip().casefold() in {"n/a", "na"} for c in w["credits"]) else "blank-credit-field" if w.get("blankCreditCount") else "no-credited-person",
        "context": w["context"]} for p, w in winners if not w["credits"] or w.get("blankCreditCount") or any(c["name"].strip().casefold() in {"n/a", "na"} for c in w["credits"])]
    diagnostics = [{"year": p["year"], "sourceUrl": p["sourceUrl"], "diagnostics": p["sourceDiagnostics"]}
                   for p in snapshot["pages"] if p["sourceDiagnostics"]]
    failure_kinds = Counter(f["kind"] for f in snapshot["failures"])
    indexed_urls = {c["url"] for y in index["years"] for c in y["categories"]}
    no_award_urls = {p["sourceUrl"] for p in snapshot.get("noAwardPages", [])}
    conflicts = {f["input"]["url"] for f in snapshot["failures"] if f["kind"] == "source-conflict"}
    exceptions = []
    for value in lineage.get("annualExceptions", []):
        url = f"https://www.televisionacademy.com/awards/nominees-winners/{value['year']}/{value['sourceSlug']}"
        status = "source-conflict" if url in conflicts else "reconciled-no-award-page" if url in no_award_urls else "explicit-no-award-without-index-page" if url not in indexed_urls else "unresolved-source-page"
        exceptions.append({**value, "reconciliationStatus": status})
    allocated = [(p, category_for_year(by_slug[p["sourceUrl"].rsplit('/', 1)[1]], p["year"])) for p in snapshot["pages"]]
    allocated = [(p, category) for p, category in allocated if category]
    categories = []
    for category in registry["included"]:
        category_pages = [p for p, target in allocated if target == category["id"]]
        categories.append({"id": category["id"], "name": category["name"],
            "historyStatus": "incomplete-history-review", "reviewedSourcePageCount": len(category_pages),
            "reviewedWinnerAllocationCount": sum(p["winnerCount"] for p in category_pages),
            "reviewedSourceYears": sorted({p["year"] for p in category_pages}, reverse=True),
            "policy": "These are accepted page allocations only. Pending mixed predecessors, failed extraction and production/recipient identity review still block a complete catalogue history."})
    years = []
    for entry in index["years"]:
        pages = [p for p in snapshot["pages"] if p["year"] == entry["year"]]
        failures = [f for f in snapshot["failures"] if f["input"]["year"] == entry["year"]]
        years.append({"year": entry["year"], "annualCategoryCount": entry["categoryCount"],
            "acquiredCandidatePageCount": len(pages), "winnerRecordCount": sum(p["winnerCount"] for p in pages),
            "unresolvedSourcePageCount": len(failures)})
    return {"schemaVersion": 1, "inputSha256": inputs, "checkedAt": registry["checkedAt"],
        "policy": "Source evidence and review queue only. Historical credit gaps, missing markers and mixed lineages are not resolved identities, confirmed no-award decisions or complete catalogue histories.",
        "summary": {"selectedCurrentCategoryCount": len(registry["included"]),
            "annualIndexCount": len(index["years"]), "annualCategoryLinkCount": sum(y["categoryCount"] for y in index["years"]),
            "historicalPageSlugCount": len(decisions), "scopeExcludedSlugCount": sum(d["disposition"] == "excluded" for d in decisions),
            "pendingLineageSlugCount": sum(d["disposition"] == "pending-review" for d in decisions),
            "reviewedLineageSlugCount": sum(d["disposition"] == "current-lineage" for d in decisions),
            "reviewedAllocationPageCount": len(allocated),
            "reviewedWinnerAllocationCount": sum(p["winnerCount"] for p, _ in allocated),
            "acquiredCandidatePageCount": len(snapshot["pages"]), "candidateWinnerRecordCount": len(winners),
            "independentlyReconciledNoAwardPageCount": len(snapshot.get("noAwardPages", [])),
            "unresolvedSourcePageCount": len(snapshot["failures"]), "failureKinds": dict(sorted(failure_kinds.items())),
            "winnerCreditGapCount": len(credit_gaps), "sourceDiagnosticPageCount": len(diagnostics),
            "currentReleaseHeadingCount": releases["releaseHeadingCount"],
            "independentNoAwardStatementCount": len(exceptions),
            "publishedEmmyCatalogueCount": sum(c["id"].startswith("emmy-") for c in load(ROOT / "manifest.json")["catalogs"])},
        "years": years, "categories": categories, "annualExceptions": exceptions,
        "sourceFailures": snapshot["failures"], "noAwardPages": snapshot.get("noAwardPages", []), "winnerCreditGaps": credit_gaps,
        "sourceDiagnostics": diagnostics,
        "pendingLineages": [{"sourceSlug": d["sourceSlug"], "firstYear": d["firstYear"], "lastYear": d["lastYear"],
            "menuLabels": d["menuLabels"], "reason": d["reason"],
            **({"pendingPeriods": [{"years": p["years"], "reason": p["reason"]} for p in d["periods"] if p["disposition"] == "pending-review"]} if "periods" in d else {})}
            for d in decisions if d["disposition"] == "pending-review"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        parser.error("choose --write or --check")
    report = build()
    content = serialized(report)
    if args.write:
        REPORT_PATH.write_text(content, encoding="utf-8")
    if args.check and REPORT_PATH.read_text(encoding="utf-8") != content:
        raise ValueError("Emmy source review report is stale")
    print(serialized(report["summary"]))


if __name__ == "__main__":
    main()
