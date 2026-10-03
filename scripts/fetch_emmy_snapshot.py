#!/usr/bin/env python3
"""Acquire cached official Emmy indices and reviewable winner-only snapshots.

Maintenance-only HTTPS; CI uses committed evidence. No TMDB award scraping.
Candidate page-slug continuity does not constitute a reviewed lineage decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from emmy_source import SourceError, YEAR_TEMPLATE, annual_categories, category_results

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


def acquire_page(entry: dict, cache: Path, offline: bool) -> dict:
    html, evidence = source_html(entry["url"], cache, offline)
    try:
        result = category_results(html, entry["year"], entry["url"])
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
            if decision["disposition"] == "excluded":
                continue
            if "acquisitionYears" in decision and index["year"] not in decision["acquisitionYears"]:
                continue
            pages.append({"year": index["year"], **category})
    return pages


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
                    "kind": "extraction-error" if isinstance(exc, SourceError) else "http-error" if isinstance(exc, HTTPError) else "external-service-error",
                    "checkedAt": datetime.now(timezone.utc).date().isoformat()}
                if isinstance(exc, HTTPError):
                    failure["status"] = exc.code
                if hasattr(exc, "source_evidence"):
                    failure["source"] = exc.source_evidence
                    failure["checkedAt"] = exc.source_evidence["checkedAt"]
                if hasattr(exc, "details"):
                    failure["rejectedPageEvidence"] = exc.details
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
    pages = candidate_pages(indices, lineage)
    values, errors = run_batch(pages, lambda entry: acquire_page(entry, args.cache_dir, args.offline), args.workers)
    values.sort(key=lambda entry: (-entry["year"], entry["sourceUrl"]))
    snapshot = {"schemaVersion": 1, "source": registry["authority"], "requestedYears": years,
                "policy": "Winner-only source facts. Candidate page continuity remains pending explicit historical lineage review; this is not canonical identity data.",
                "completeAcquisition": not errors, "pageCount": len(values),
                "winnerRecordCount": sum(value["winnerCount"] for value in values), "pages": values, "failures": errors}
    content = serialized(snapshot)
    if args.check:
        if SNAPSHOT_PATH.read_text(encoding="utf-8") != content:
            raise SourceError("winner snapshot evidence is stale")
    else:
        SNAPSHOT_PATH.write_text(content, encoding="utf-8")
    action = "Verified saved" if args.check else "Wrote"
    print(f"{action} {len(values)} candidate pages and {snapshot['winnerRecordCount']} official winners; errors {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
