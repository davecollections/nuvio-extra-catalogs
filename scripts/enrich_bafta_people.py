#!/usr/bin/env python3
"""Resolve BAFTA actors/directors only through credits of reviewed winning works.

This maintenance command uses the shared live TMDB client. It never resolves a
person by name alone or treats a missing credit as proof of a missing identity.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from bafta_common import SOURCE_DIR, load_json, selected_winners, work_key
from build_bafta_identity_seed import recipient_key
from enrich_bafta_identities import api_json
from enrich_golden_globes_identities import normalized_title

PATH = SOURCE_DIR / "identity-map.json"
ROLES = {"actor", "director"}


def contexts(identity_map: dict) -> dict[str, list[dict]]:
    works = {entry["key"]: entry for entry in identity_map["works"]}
    result: dict[str, list[dict]] = {}
    for winner in selected_winners():
        role = winner["category"].get("creditRole")
        if role not in ROLES:
            continue
        resolution = works[work_key(winner)].get("resolution", {})
        for name in winner["recipientValues"]:
            key = recipient_key(name, winner["nominationId"])
            result.setdefault(key, []).append({
                "name": name, "role": role,
                "nominationId": winner["nominationId"],
                "workTitle": winner["workTitle"],
                "mediaType": resolution.get("mediaType"),
                "tmdbId": resolution.get("tmdbId"),
                "imdbId": resolution.get("imdbId"),
            })
    return result


def validate(identity_map: dict) -> tuple[int, int]:
    scoped = contexts(identity_map)
    resolved = 0
    for entry in identity_map["recipients"]:
        if entry["key"] not in scoped or "resolution" not in entry:
            continue
        value = entry["resolution"]
        if not isinstance(value.get("tmdbId"), int) or value["tmdbId"] <= 0:
            raise ValueError(f"Invalid TMDB person: {entry['key']}")
        if value.get("imdbId") and not re.fullmatch(r"nm\d+", value["imdbId"]):
            raise ValueError(f"Invalid IMDb person: {entry['key']}")
        if value.get("method") != "exact-name-and-awarded-work-credit":
            raise ValueError(f"Unexpected person review method: {entry['key']}")
        evidence = value.get("creditEvidence", [])
        if not evidence:
            raise ValueError(f"Missing work-credit evidence: {entry['key']}")
        for item in evidence:
            if item.get("tmdbPersonId") != value["tmdbId"] or not any(
                context["nominationId"] == item.get("nominationId")
                and context["role"] == item.get("role")
                and context["tmdbId"] == item.get("tmdbWorkId")
                and context["imdbId"] == item.get("imdbWorkId")
                and context["mediaType"] == item.get("mediaType")
                and normalized_title(context["name"]) == normalized_title(item.get("creditName", ""))
                for context in scoped[entry["key"]]
            ):
                raise ValueError(f"Stale or mismatched work-credit evidence: {entry['key']}")
        resolved += 1
    return len(scoped), resolved


def enrich(identity_map: dict, workers: int) -> None:
    token = os.environ["TMDB_API_READ_TOKEN"]
    scoped = contexts(identity_map)
    work_ids = sorted({
        (context["mediaType"], context["tmdbId"])
        for entries in scoped.values() for context in entries if context["tmdbId"]
    })

    def fetch_work(key: tuple[str, int]) -> tuple[tuple[str, int], tuple[str, dict]]:
        media, work_id = key
        path = f"/{'tv' if media == 'series' else 'movie'}/{work_id}/{'aggregate_credits' if media == 'series' else 'credits'}"
        return key, (path, api_json(path, token))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        credits = {}
        for key, value in pool.map(fetch_work, work_ids):
            credits[key] = value
            if len(credits) % 50 == 0:
                print(f"Read live credits for {len(credits)}/{len(work_ids)} works", flush=True)

    candidates: dict[str, dict[int, list[dict]]] = {}
    for key, entries in scoped.items():
        found: dict[int, list[dict]] = {}
        for context in entries:
            if not context["tmdbId"]:
                continue
            path, payload = credits[(context["mediaType"], context["tmdbId"])]
            source = payload.get("cast" if context["role"] == "actor" else "crew", [])
            for person in source:
                jobs = [person.get("job"), *[job.get("job") for job in person.get("jobs", [])]]
                if context["role"] == "director" and "Director" not in jobs:
                    continue
                if normalized_title(person.get("name", "")) != normalized_title(context["name"]):
                    continue
                found.setdefault(person["id"], []).append({
                    "nominationId": context["nominationId"], "role": context["role"],
                    "tmdbWorkId": context["tmdbId"], "imdbWorkId": context["imdbId"],
                    "mediaType": context["mediaType"], "tmdbPersonId": person["id"],
                    "creditName": person["name"],
                    "sourceUrl": "https://api.themoviedb.org/3" + path,
                })
        candidates[key] = found
    unique_ids = sorted({next(iter(found)) for found in candidates.values() if len(found) == 1})

    def fetch_person(person_id: int) -> tuple[int, dict]:
        return person_id, api_json(f"/person/{person_id}", token, {"append_to_response": "external_ids"})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        people = dict(pool.map(fetch_person, unique_ids))
    for entry in identity_map["recipients"]:
        if entry["key"] not in candidates:
            continue
        found = candidates[entry["key"]]
        if len(found) != 1:
            # Never silently replace a prior reviewed resolution after a live change.
            if "resolution" in entry:
                raise ValueError(f"Existing person resolution needs review: {entry['key']}")
            entry["candidates"] = [{"tmdbId": person_id, "creditEvidence": evidence}
                                   for person_id, evidence in sorted(found.items())]
            continue
        person_id = next(iter(found))
        person = people[person_id]
        imdb = person.get("external_ids", {}).get("imdb_id") or person.get("imdb_id")
        resolution = {
            "name": person["name"], "tmdbId": person_id,
            **({"imdbId": imdb} if imdb else {}),
            "method": "exact-name-and-awarded-work-credit",
            "checkedAt": date.today().isoformat(),
            "creditEvidence": sorted(found[person_id], key=lambda item: (item["nominationId"], item["tmdbWorkId"])),
        }
        if entry.get("resolution", {}).get("tmdbId", person_id) != person_id:
            raise ValueError(f"Conflicting person resolution: {entry['key']}")
        entry["resolution"] = resolution
        entry.pop("candidates", None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tmdb", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if not (args.tmdb or args.check) or args.workers < 1:
        parser.error("choose --tmdb or --check and a positive worker count")
    identity_map = load_json(PATH)
    if args.tmdb:
        enrich(identity_map, args.workers)
    total, resolved = validate(identity_map)
    if args.tmdb:
        PATH.write_text(json.dumps(identity_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"BAFTA actor/director identities: {resolved}/{total} resolved; {total-resolved} require review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
