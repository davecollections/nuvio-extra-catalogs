#!/usr/bin/env python3
"""Review live work identity and poster evidence across every published award.

This complements the programme generators: an image loading is not proof that
the selected production is correct. It never applies candidates automatically.
The existing TMDB client and MetaHub checker remain the production audit paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bafta_artwork import POSTER_TEMPLATE, check_metahub
from bafta_common import ROOT, load_json
from enrich_bafta_identities import api_json
from enrich_golden_globes_identities import normalized_title

REPORT = ROOT / "reports" / "awards-work-mapping-audit.json"


def inventory() -> tuple[dict[str, dict], str]:
    entries: dict[str, dict] = {}
    paths = {ROOT / "manifest.json"}
    for catalog in load_json(ROOT / "manifest.json")["catalogs"]:
        path = ROOT / "catalog" / catalog["type"] / f"{catalog['id']}.json"
        paths.add(path)
        for meta in load_json(path)["metas"]:
            key = f"{catalog['type']}:{meta['id']}"
            entry = entries.setdefault(key, {
                "imdbId": meta["id"], "mediaType": catalog["type"],
                **{field: set() for field in (
                    "titles", "posterUrls", "catalogIds", "tmdbIds",
                    "releaseYears", "awardBodies", "awardYears", "sourceFiles",
                )},
            })
            entry["titles"].add(meta["name"])
            entry["posterUrls"].add(meta["poster"])
            entry["catalogIds"].add(catalog["id"])
    for path in sorted((ROOT / "data" / "awards").glob("*/results/*.json")):
        paths.add(path)
        data = load_json(path)
        for result in data["results"]:
            for work in result.get("works", [result.get("work")]):
                if not isinstance(work, dict) or not work.get("imdbId"):
                    continue
                key = f"{work['mediaType']}:{work['imdbId']}"
                if key not in entries:
                    continue
                entry = entries[key]
                entry["titles"].add(work["title"])
                for field, singular in (("tmdbIds", "tmdbId"), ("releaseYears", "releaseYear")):
                    if work.get(singular) is not None:
                        entry[field].add(work[singular])
                entry["awardBodies"].add(data["awardBodyId"])
                entry["awardYears"].add(data["ceremony"]["year"])
                entry["sourceFiles"].add(path.relative_to(ROOT).as_posix())
    for entry in entries.values():
        for field, value in entry.items():
            if isinstance(value, set):
                entry[field] = sorted(value)
        if not entry["sourceFiles"]:
            raise ValueError(f"Published identity has no canonical source: {entry['imdbId']}")
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        # Hash semantic JSON so Windows checkout line endings do not matter.
        digest.update(json.dumps(load_json(path), sort_keys=True, ensure_ascii=False).encode())
    return dict(sorted(entries.items())), digest.hexdigest()


def summary_record(data: dict, kind: str) -> dict:
    aliases = data.get("alternative_titles") or data.get("alternative_names") or {}
    if isinstance(aliases, dict):
        aliases = aliases.get("titles", aliases.get("results", []))
    return {
        "tmdbId": data.get("id"), "mediaType": "series" if kind == "tv" else kind,
        "title": data.get("title") or data.get("name"),
        "originalTitle": data.get("original_title") or data.get("original_name"),
        "releaseDate": data.get("release_date") or data.get("first_air_date"),
        "imdbId": (data.get("external_ids") or {}).get("imdb_id") or data.get("imdb_id"),
        "posterPath": data.get("poster_path"),
        "alternativeTitles": sorted({a.get("title") or a.get("name") for a in aliases if a.get("title") or a.get("name")}),
    }


def image_check(url: str, imdb_id: str) -> dict:
    if url == POSTER_TEMPLATE.format(imdb_id=imdb_id):
        return check_metahub(imdb_id)
    try:
        with urlopen(Request(url, method="HEAD", headers={"User-Agent": "Xtra-BAFTA-artwork-audit/1.0"}), timeout=25) as response:
            return {"url": url, "status": response.status, "contentType": response.headers.get("Content-Type", "")}
    except HTTPError as exc:
        if exc.code != 404:
            raise
        return {"url": url, "status": 404, "contentType": exc.headers.get("Content-Type", "")}


def inspect(entry: dict, token: str) -> dict:
    kind = "tv" if entry["mediaType"] == "series" else "movie"
    mapped = []
    for tmdb_id in entry["tmdbIds"]:
        data = api_json(f"/{kind}/{tmdb_id}", token, {
            "append_to_response": "external_ids,alternative_titles" if kind == "movie" else "external_ids,alternative_names",
            "language": "en-US",
        })
        mapped.append(summary_record(data, kind))
    found = api_json(f"/find/{entry['imdbId']}", token, {"external_source": "imdb_id"})
    candidates = []
    for result_kind, field in (("movie", "movie_results"), ("tv", "tv_results"), ("tv_episode", "tv_episode_results")):
        for result in found.get(field, []):
            candidate = summary_record(result, result_kind)
            if result_kind == "tv_episode":
                candidate.update({k: result.get(k) for k in ("show_id", "season_number", "episode_number")})
            candidates.append(candidate)
    posters = [image_check(url, entry["imdbId"]) for url in entry["posterUrls"]]
    searched = []
    if not mapped or any(p["status"] == 404 for p in posters):
        for title in entry["titles"][:2]:
            data = api_json(f"/search/{kind}", token, {"query": title, "language": "en-US", "include_adult": "false"})
            searched.append({"query": title, "totalResults": data.get("total_results"), "results": [summary_record(r, kind) for r in data.get("results", [])]})
    return {"mapped": mapped, "externalLookup": candidates, "posters": posters, "titleSearch": searched}


def flags(entry: dict, evidence: dict) -> list[str]:
    result = []
    if evidence.get("error"):
        return ["external-service-error"]
    if len(entry["tmdbIds"]) > 1:
        result.append("conflicting-canonical-tmdb-ids")
    if entry["releaseYears"] and min(entry["releaseYears"]) > min(entry["awardYears"]):
        result.append("canonical-release-after-award-review")
    if not evidence["mapped"]:
        result.append("no-reviewed-tmdb-mapping")
    normalized = {normalized_title(t) for t in entry["titles"]}
    for mapped in evidence["mapped"]:
        if mapped["imdbId"] != entry["imdbId"]:
            result.append("tmdb-imdb-conflict" if mapped["imdbId"] else "tmdb-imdb-link-absent")
        names = [mapped["title"], mapped["originalTitle"], *mapped["alternativeTitles"]]
        if not any(normalized_title(t) in normalized for t in names if t):
            result.append("title-review")
        year = int(mapped["releaseDate"][:4]) if mapped.get("releaseDate") else None
        if year and entry["releaseYears"] and any(abs(year - old) > 1 for old in entry["releaseYears"]):
            result.append("release-year-review")
        if year and year > min(entry["awardYears"]):
            result.append("release-after-award-review")
    matches = [r for r in evidence["externalLookup"] if r["mediaType"] == entry["mediaType"]]
    if evidence["externalLookup"] and not matches:
        result.append("external-lookup-media-review")
    if matches and entry["tmdbIds"] and not any(r["tmdbId"] in entry["tmdbIds"] for r in matches):
        result.append("external-lookup-id-review")
    if any(p["status"] != 200 or not p["contentType"].startswith("image/") for p in evidence["posters"]):
        result.append("poster-unavailable")
    return sorted(set(result))


def review_basis(row: dict) -> str:
    """Invalidate a decision when its actual identity or live evidence changes."""
    data = {field: row[field] for field in ("inventory", "evidence", "flags")}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_review(key: str, row: dict) -> None:
    if not row["flags"]:
        return
    review = row.get("review", {})
    notes = review.get("flagNotes", {})
    if review.get("basisSha256") != review_basis(row) or set(notes) != set(row["flags"]):
        raise ValueError(f"Missing or stale flag review: {key}")
    if not all(isinstance(note, str) and note.strip() for note in notes.values()):
        raise ValueError(f"Empty flag review: {key}")


def write_report(report: dict) -> None:
    # One entry per line, following the existing compact canonical-data convention.
    header = json.dumps({k: v for k, v in report.items() if k != "entries"}, ensure_ascii=False, indent=2)[:-2]
    rendered = header + ',\n  "entries": {\n' + ',\n'.join('    ' + json.dumps(k) + ': ' + json.dumps(v, ensure_ascii=False, separators=(',', ':')) for k, v in report["entries"].items()) + '\n  }\n}\n'
    REPORT.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, help="Live evidence checkpoint; retain between interrupted runs.")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--offline-check", action="store_true")
    args = parser.parse_args()
    entries, digest = inventory()
    if args.offline_check:
        report = load_json(REPORT)
        if report.get("inputSha256") != digest or set(report["entries"]) != set(entries):
            raise ValueError("Work mapping audit is stale or incomplete")
        for key, entry in entries.items():
            row = report["entries"][key]
            if row["inventory"] != entry or row["flags"] != flags(entry, row["evidence"]):
                raise ValueError(f"Stale audit evidence: {key}")
            if "external-service-error" in row["flags"]:
                raise ValueError(f"Unresolved service error: {key}")
            validate_review(key, row)
        print(f"Work mapping audit covers all {len(entries)} published identities with recorded flag dispositions.")
        return 0
    if not 1 <= args.workers <= 16:
        raise ValueError("workers must be between 1 and 16")
    token = os.environ["TMDB_API_READ_TOKEN"]
    cache = load_json(args.cache) if args.cache and args.cache.exists() else {}
    rows = {}
    pending = []
    for key, entry in entries.items():
        signature = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        old = cache.get(key, {})
        if old.get("signature") == signature and not old.get("evidence", {}).get("error"):
            rows[key] = old
        else:
            pending.append((key, entry, signature))
    print(f"Checking {len(pending)} identities; reusing {len(rows)} unchanged live checkpoints", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(inspect, e, token): (k, e, s) for k, e, s in pending}
        for number, future in enumerate(as_completed(futures), 1):
            key, entry, signature = futures[future]
            try:
                evidence = future.result()
            except Exception as exc:
                evidence = {"error": f"{type(exc).__name__}: {exc}"}
            rows[key] = {"signature": signature, "checkedAt": datetime.now(timezone.utc).isoformat(), "evidence": evidence}
            if args.cache and (number % 50 == 0 or number == len(pending)):
                args.cache.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            if number % 100 == 0 or number == len(pending):
                print(f"Checked {number}/{len(pending)} identities", flush=True)
    report = {"schemaVersion": 1, "scope": "Every published work, across all award bodies; person identities excluded.",
        "inputSha256": digest, "entries": {k: {"inventory": entries[k], "checkedAt": rows[k]["checkedAt"],
            "evidence": rows[k]["evidence"], "flags": flags(entries[k], rows[k]["evidence"])} for k in entries}}
    previous = load_json(REPORT) if REPORT.exists() else {}
    for key, row in report["entries"].items():
        old_review = previous.get("entries", {}).get(key, {}).get("review", {})
        if old_review.get("basisSha256") == review_basis(row):
            row["review"] = old_review
    write_report(report)
    errors = sum("external-service-error" in r["flags"] for r in report["entries"].values())
    print(f"Wrote evidence for {len(entries)} identities ({errors} service errors).", flush=True)
    print("Review new/changed flags before running --offline-check.", flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
