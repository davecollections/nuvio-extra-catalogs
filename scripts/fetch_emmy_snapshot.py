#!/usr/bin/env python3
"""Acquire cached official Emmy indices and reviewable winner-only snapshots.

Maintenance-only HTTPS; CI uses committed evidence. No TMDB award scraping.
Candidate page-slug continuity does not constitute a reviewed lineage decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from emmy_source import SourceError, YEAR_TEMPLATE, annual_categories, category_results, normalized

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "sources" / "emmys"
REGISTRY_PATH = SOURCE_DIR / "current-category-pages.json"
INDEX_PATH = SOURCE_DIR / "annual-indices.json"
SNAPSHOT_PATH = SOURCE_DIR / "official-winners-1949-2026.json"


def serialized(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def source_html(url: str, cache: Path, offline: bool) -> tuple[str, dict]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "www.televisionacademy.com":
        raise SourceError(f"unsupported source URL: {url}")
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    html_path, evidence_path = cache / (key + ".html"), cache / (key + ".json")
    if html_path.exists() and evidence_path.exists():
        raw, evidence = html_path.read_bytes(), load(evidence_path)
        if evidence.get("url") != url or hashlib.sha256(raw).hexdigest() != evidence.get("sha256"):
            raise SourceError(f"{url}: cached response/hash mismatch")
        return raw.decode("utf-8"), evidence
    if offline:
        raise SourceError(f"{url}: uncached official response in offline mode")
    request = Request(url, headers={"Accept": "text/html", "User-Agent": "nuvio-extra-catalogs-reviewed-maintenance/1.0"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200 or response.headers.get_content_type() != "text/html":
            raise SourceError(f"{url}: unexpected response status/type")
        if urlparse(response.url).netloc != parsed.netloc:
            raise SourceError(f"{url}: source redirected outside approved authority")
        raw = response.read()
        evidence = {"url": url, "resolvedUrl": response.url, "status": response.status,
                    "checkedAt": datetime.now(timezone.utc).date().isoformat(),
                    "sha256": hashlib.sha256(raw).hexdigest(), "byteCount": len(raw)}
    html = raw.decode("utf-8")
    # Cache only verified ceremony pages; challenge/error HTML is never evidence.
    year = int(parsed.path.split("/")[3])
    from emmy_source import document
    document(html, year)
    cache.mkdir(parents=True, exist_ok=True)
    html_path.write_bytes(raw)
    evidence_path.write_text(serialized(evidence), encoding="utf-8")
    time.sleep(0.3)
    return html, evidence


def acquire_index(year: int, cache: Path, offline: bool) -> dict:
    url = YEAR_TEMPLATE.format(year=year)
    html, evidence = source_html(url, cache, offline)
    categories = annual_categories(html, year)
    return {"year": year, "ceremonyNumber": year - 1948, "source": evidence,
            "categoryCount": len(categories), "categories": categories}


def no_award_exceptions(lineage):
    """Only pinned, independently explicit notices can reconcile absent markers."""
    contexts = {s["url"]: s for s in lineage.get("contextSources", [])}
    exceptions = {}
    for value in lineage.get("annualExceptions", []):
        context = contexts[value["sourceUrl"]]
        require_statement = re.search(r"no emmys?(?: are| is)? (?:awarded|given)", value["proof"], re.I)
        if (value["outcome"] != "no-award" or not require_statement or
                value["proof"] not in context["context"] or str(value["year"]) not in value["proof"] or
                normalized(value["sourceCategory"]) not in normalized(value["proof"]) or
                hashlib.sha256(context["context"].encode("utf-8")).hexdigest() != context["contextSha256"]):
            raise SourceError("historical no-award exception lacks explicit pinned independent evidence")
        url = YEAR_TEMPLATE.format(year=value["year"]) + "/" + value["sourceSlug"]
        if url in exceptions:
            raise SourceError("duplicate no-award exception")
        exceptions[url] = value
    return exceptions


def apply_no_award_evidence(page, exception):
    if page["year"] != exception["year"] or page["sourceUrl"].rsplit('/', 1)[1] != exception["sourceSlug"]:
        raise SourceError("no-award evidence belongs to a different ceremony/category")
    if normalized(page["sourceCategory"]) != normalized(exception["sourceCategory"]):
        raise SourceError("no-award evidence names a different official category heading")
    if page["winnerCount"] or page["winnerGridCount"]:
        error = SourceError(f"{page['sourceUrl']}: HTML winner markers conflict with the independent official no-award statement")
        error.conflicting_winner_evidence = {"html": page, "independentNoAward": exception}
        raise error
    return {**page, "outcome": "no-award", "independentNoAward": exception}


def acquire_page(entry: dict, cache: Path, offline: bool, exceptions=None) -> dict:
    html, evidence = source_html(entry["url"], cache, offline)
    exception = (exceptions or {}).get(entry["url"])
    try:
        try:
            result = category_results(html, entry["year"], entry["url"])
        except SourceError as exc:
            if exception is None or not hasattr(exc, "details") or exc.details["winnerGridCount"]:
                raise
            details = exc.details
            result = {"year": entry["year"], "ceremonyNumber": entry["year"] - 1948,
                "sourceUrl": entry["url"], **{k: v for k, v in details.items() if k != "nominations"},
                "winnerCount": 0, "winners": [], "nominationEvidence": details["nominations"],
                "sourceDiagnostics": ["Absent HTML winner markers independently reconciled by the pinned official no-award statement"]}
        if exception:
            result = apply_no_award_evidence(result, exception)
    except SourceError as exc:
        exc.source_evidence = evidence
        raise
    return {**result, "source": evidence, "lineageStatus": "pending-review"}


def candidate_pages(indices, lineage):
    decisions = {d["sourceSlug"]: d for p in lineage["programmes"] for d in p["decisions"]}
    pages = []
    for index in indices:
        for category in index["categories"]:
            decision = decisions[category["slug"]]
            # Reviewed scope exclusions may explicitly retain their acquired
            # evidence. Exclusion controls output eligibility, not erasure of
            # facts already inspected for a historical boundary decision.
            if decision["disposition"] == "excluded" and "acquisitionYears" not in decision:
                continue
            if "acquisitionYears" in decision and index["year"] not in decision["acquisitionYears"]:
                continue
            pages.append({"year": index["year"], **category})
    return pages


def review_for_year(decision, year):
    """Read explicit review periods; never infer a target from a page slug."""
    if not decision["firstYear"] <= year <= decision["lastYear"]:
        return None
    if "acquisitionYears" in decision and year not in decision["acquisitionYears"]:
        return None
    if "periods" not in decision:
        return decision
    matches = [period for period in decision["periods"] if year in period["years"]]
    if len(matches) != 1:
        raise SourceError(f"{decision['sourceSlug']}/{year}: missing or overlapping review period")
    return matches[0]


def category_for_year(decision, year):
    review = review_for_year(decision, year)
    if review and review["disposition"] == "current-lineage":
        return review.get("currentCategory")
    return None


def category_for_winner(decision, year, source_key):
    """Mixed historical fields require an exact allocation for each winner."""
    review = review_for_year(decision, year)
    if not review or review["disposition"] != "current-lineage":
        return None
    if "winnerAllocations" not in review:
        return category_for_year(decision, year)
    matches = [value for value in review["winnerAllocations"] if value["sourceKey"] == source_key and value["year"] == year]
    if len(matches) != 1:
        raise SourceError(f"{decision['sourceSlug']}/{year}: missing or duplicate winner allocation")
    allocation = matches[0]
    return allocation.get("currentCategory") if allocation["disposition"] == "current-lineage" else None


def run_batch(entries, operation, workers):
    values, failures = [], []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(operation, entry): entry for entry in entries}
        for future in as_completed(futures):
            entry = futures[future]
            try:
                values.append(future.result())
            except (SourceError, HTTPError, URLError, TimeoutError, UnicodeError, ValueError) as exc:
                failure = {"input": entry, "error": str(exc),
                    "kind": "source-conflict" if hasattr(exc, "conflicting_winner_evidence") else "extraction-error" if isinstance(exc, SourceError) else "http-error" if isinstance(exc, HTTPError) else "external-service-error",
                    "checkedAt": datetime.now(timezone.utc).date().isoformat()}
                if isinstance(exc, HTTPError):
                    failure["status"] = exc.code
                if hasattr(exc, "source_evidence"):
                    failure["source"] = exc.source_evidence
                    failure["checkedAt"] = exc.source_evidence["checkedAt"]
                if hasattr(exc, "details"):
                    failure["rejectedPageEvidence"] = exc.details
                if hasattr(exc, "conflicting_winner_evidence"):
                    failure["conflictingWinnerEvidence"] = exc.conflicting_winner_evidence
                failures.append(failure)
                print(f"ERROR {entry}: {exc}", flush=True)
            if len(values) % 25 == 0 or len(values) + len(failures) == len(entries):
                print(f"Processed {len(values) + len(failures)}/{len(entries)}; errors {len(failures)}", flush=True)
    failures.sort(key=lambda f: json.dumps(f["input"], sort_keys=True))
    return values, failures


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2026, 1948, -1)))
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--indices-only", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--check", action="store_true", help="compare generated evidence with saved files without writing")
    args = parser.parse_args()
    years = sorted(set(args.years), reverse=True)
    if any(year < 1949 or year > 2026 for year in years) or not 1 <= args.workers <= 4:
        parser.error("years must be 1949–2026 and workers 1–4")
    registry = load(REGISTRY_PATH)
    indices, errors = run_batch(years, lambda year: acquire_index(year, args.cache_dir, args.offline), args.workers)
    indices.sort(key=lambda entry: entry["year"], reverse=True)
    index = {"schemaVersion": 1, "authority": registry["authority"], "requestedYears": years,
             "complete": not errors, "years": indices, "failures": errors}
    index_content = serialized(index)
    if args.check:
        if INDEX_PATH.read_text(encoding="utf-8") != index_content:
            raise SourceError("annual index evidence is stale")
    else:
        INDEX_PATH.write_text(index_content, encoding="utf-8")
    if errors:
        print("ERROR: annual acquisition incomplete; failures retained, never treated as no-award years")
        return 1
    if args.indices_only:
        action = "Verified saved" if args.check else "Wrote"
        print(f"{action} {len(indices)} annual indices, {sum(y['categoryCount'] for y in indices)} category links")
        return 0
    lineage = load(SOURCE_DIR / "lineage-decisions.json")
    exceptions = no_award_exceptions(lineage)
    pages = candidate_pages(indices, lineage)
    values, errors = run_batch(pages, lambda entry: acquire_page(entry, args.cache_dir, args.offline, exceptions), args.workers)
    values.sort(key=lambda entry: (-entry["year"], entry["sourceUrl"]))
    no_awards = [value for value in values if value.get("outcome") == "no-award"]
    values = [value for value in values if value.get("outcome") != "no-award"]
    snapshot = {"schemaVersion": 1, "source": registry["authority"], "requestedYears": years,
                "policy": "Winner-only source facts. Candidate page continuity remains pending explicit historical lineage review; this is not canonical identity data.",
                "completeAcquisition": not errors, "pageCount": len(values),
                "winnerRecordCount": sum(value["winnerCount"] for value in values), "pages": values,
                "noAwardPages": no_awards, "failures": errors}
    content = serialized(snapshot)
    if args.check:
        if SNAPSHOT_PATH.read_text(encoding="utf-8") != content:
            raise SourceError("winner snapshot evidence is stale")
    else:
        SNAPSHOT_PATH.write_text(content, encoding="utf-8")
    action = "Verified saved" if args.check else "Wrote"
    print(f"{action} {len(values)} winner pages, {len(no_awards)} independently reconciled no-award pages and {snapshot['winnerRecordCount']} source winners; errors {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
