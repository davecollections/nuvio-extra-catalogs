#!/usr/bin/env python3
"""Deterministic source-review report; source acquisition is not acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from fetch_emmy_snapshot import INDEX_PATH, REGISTRY_PATH, SNAPSHOT_PATH, SOURCE_DIR, load, serialized

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
    winners = [(p, w) for p in snapshot["pages"] for w in p["winners"]]
    credit_gaps = [{"year": p["year"], "sourceCategory": p["sourceCategory"], "sourceUrl": p["sourceUrl"],
        "sourceKey": w["sourceKey"], "heading": w["heading"],
        "issue": "blank-credit-field" if w.get("blankCreditCount") else "no-credited-person",
        "context": w["context"]} for p, w in winners if not w["credits"] or w.get("blankCreditCount")]
    diagnostics = [{"year": p["year"], "sourceUrl": p["sourceUrl"], "diagnostics": p["sourceDiagnostics"]}
                   for p in snapshot["pages"] if p["sourceDiagnostics"]]
    failure_kinds = Counter(f["kind"] for f in snapshot["failures"])
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
            "acquiredCandidatePageCount": len(snapshot["pages"]), "candidateWinnerRecordCount": len(winners),
            "unresolvedSourcePageCount": len(snapshot["failures"]), "failureKinds": dict(sorted(failure_kinds.items())),
            "winnerCreditGapCount": len(credit_gaps), "sourceDiagnosticPageCount": len(diagnostics),
            "currentReleaseHeadingCount": releases["releaseHeadingCount"],
            "publishedEmmyCatalogueCount": sum(c["id"].startswith("emmy-") for c in load(ROOT / "manifest.json")["catalogs"])},
        "years": years, "sourceFailures": snapshot["failures"], "winnerCreditGaps": credit_gaps,
        "sourceDiagnostics": diagnostics,
        "pendingLineages": [{"sourceSlug": d["sourceSlug"], "firstYear": d["firstYear"], "lastYear": d["lastYear"],
            "menuLabels": d["menuLabels"], "reason": d["reason"]} for d in decisions if d["disposition"] == "pending-review"]}


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
