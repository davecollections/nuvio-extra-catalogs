#!/usr/bin/env python3
"""Temporary Issue #4 bootstrap: enrich Best Actor winners and update canonical ceremony files."""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "data" / "awards" / "academy-awards" / "results"
GENERATED_DIR = ROOT / "data" / "generated"
REPORTS_DIR = ROOT / "reports"
OSCARS_CSV_URL = "https://raw.githubusercontent.com/DLu/oscar_data/main/oscars.csv"
PEOPLE_URL = "https://raw.githubusercontent.com/davecollections/nuvio-people-assets/main/data/people.json"
TMDB_PROXY = "https://tmdb-id-lookup-proxy.dpegan20.workers.dev"
CATEGORY = "ACTOR IN A LEADING ROLE"
EXPECTED_CEREMONIES = set(range(1, 99))
LATEST_FALLBACK = {
    "Ceremony": "98",
    "Film": "Sinners",
    "FilmId": "tt31193180",
    "Name": "Michael B. Jordan",
    "Nominees": "Michael B. Jordan",
    "NomineeIds": "",
    "Winner": "True",
}


def fetch_bytes(url: str, attempts: int = 5) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "nuvio-extra-catalogs/issue-4"})
    delay = 2
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < attempts:
                retry = int(exc.headers.get("Retry-After", delay))
                time.sleep(max(retry, delay))
                delay *= 2
                continue
            raise
        except urllib.error.URLError:
            if attempt == attempts:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"Unable to fetch {url}")


def fetch_json(url: str) -> dict:
    return json.loads(fetch_bytes(url).decode("utf-8"))


def tmdb(path: str, params: dict[str, str] | None = None) -> dict:
    url = TMDB_PROXY + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    time.sleep(0.7)
    return fetch_json(url)


def split_pipe(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split("|") if item.strip()]


def load_winners() -> list[dict[str, str]]:
    text = fetch_bytes(OSCARS_CSV_URL).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    winners = [
        row for row in rows
        if row.get("CanonicalCategory") == CATEGORY
        and str(row.get("Winner", "")).strip().lower() == "true"
        and 1 <= int(row["Ceremony"]) <= 98
    ]
    by_ceremony = {int(row["Ceremony"]) for row in winners}
    if 98 not in by_ceremony:
        winners.append(dict(LATEST_FALLBACK))
        by_ceremony.add(98)
    missing = sorted(EXPECTED_CEREMONIES - by_ceremony)
    if missing:
        raise RuntimeError(f"Missing Best Actor winner data for ceremonies: {missing}")
    if len(winners) != 99:
        raise RuntimeError(f"Expected 99 winner result rows, found {len(winners)}")
    return sorted(winners, key=lambda row: (int(row["Ceremony"]), row.get("Name", "")))


def load_people_assets() -> tuple[dict[str, dict], set[int]]:
    payload = json.loads(fetch_bytes(PEOPLE_URL).decode("utf-8"))
    people = payload.get("people", [])
    by_name = {entry["canonicalName"].casefold(): entry for entry in people}
    by_id = {int(entry["tmdbPersonId"]) for entry in people}
    return by_name, by_id


def resolve_person(name: str, imdb_id: str, artwork_by_name: dict[str, dict]) -> int:
    existing = artwork_by_name.get(name.casefold())
    if existing:
        return int(existing["tmdbPersonId"])
    if imdb_id and imdb_id != "?":
        payload = tmdb(f"/3/find/{urllib.parse.quote(imdb_id)}", {"external_source": "imdb_id"})
        results = payload.get("person_results") or []
        if len(results) == 1:
            return int(results[0]["id"])
        exact = [item for item in results if item.get("name", "").casefold() == name.casefold()]
        if len(exact) == 1:
            return int(exact[0]["id"])
    payload = tmdb("/3/search/person", {"query": name, "include_adult": "false", "language": "en-US"})
    exact = [item for item in payload.get("results", []) if item.get("name", "").casefold() == name.casefold()]
    if len(exact) != 1:
        raise RuntimeError(f"Could not uniquely resolve TMDB person for {name!r}; candidates={exact[:5]}")
    return int(exact[0]["id"])


def resolve_work(title: str, imdb_id: str) -> dict:
    if not imdb_id or imdb_id == "?":
        raise RuntimeError(f"No IMDb title ID available for winning film {title!r}")
    payload = tmdb(f"/3/find/{urllib.parse.quote(imdb_id)}", {"external_source": "imdb_id"})
    results = payload.get("movie_results") or []
    if len(results) != 1:
        raise RuntimeError(f"Expected one TMDB movie for {title!r} / {imdb_id}, got {len(results)}")
    movie = results[0]
    resolved_title = movie.get("title") or title
    if resolved_title.casefold() != title.casefold():
        aliases = {resolved_title.casefold(), (movie.get("original_title") or "").casefold()}
        if title.casefold() not in aliases:
            print(f"warning: title differs for {imdb_id}: Academy={title!r}, TMDB={resolved_title!r}")
    work = {"mediaType": "movie", "title": title, "tmdbId": int(movie["id"]), "imdbId": imdb_id}
    release_date = movie.get("release_date") or ""
    if len(release_date) >= 4 and release_date[:4].isdigit():
        work["releaseYear"] = int(release_date[:4])
    return work


def ceremony_file(ceremony_number: int) -> Path:
    matches = sorted(RESULTS_DIR.glob(f"{ceremony_number:03d}-*.json"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one result file for ceremony {ceremony_number}, found {matches}")
    return matches[0]


def main() -> None:
    winners = load_winners()
    artwork_by_name, artwork_ids = load_people_assets()
    person_cache: dict[tuple[str, str], int] = {}
    work_cache: dict[str, dict] = {}
    results_by_ceremony: dict[int, list[dict]] = {number: [] for number in EXPECTED_CEREMONIES}
    people_latest: dict[int, dict] = {}

    for row in winners:
        ceremony = int(row["Ceremony"])
        name = (row.get("Nominees") or row.get("Name") or "").strip()
        person_ids = split_pipe(row.get("NomineeIds", ""))
        imdb_person_id = person_ids[0] if person_ids else ""
        person_key = (name.casefold(), imdb_person_id)
        if person_key not in person_cache:
            person_cache[person_key] = resolve_person(name, imdb_person_id, artwork_by_name)
        tmdb_person_id = person_cache[person_key]

        titles = split_pipe(row.get("Film", ""))
        imdb_titles = split_pipe(row.get("FilmId", ""))
        if not titles:
            raise RuntimeError(f"No film attached to Best Actor winner {name} at ceremony {ceremony}")
        if len(titles) != len(imdb_titles):
            raise RuntimeError(f"Film/IMDb ID count mismatch for {name} at ceremony {ceremony}: {titles} vs {imdb_titles}")
        works = []
        for title, imdb_title_id in zip(titles, imdb_titles):
            if imdb_title_id not in work_cache:
                work_cache[imdb_title_id] = resolve_work(title, imdb_title_id)
            work = dict(work_cache[imdb_title_id])
            work["title"] = title
            works.append(work)

        result = {
            "categoryId": "best-actor",
            "status": "winner",
            "people": [{"name": name, "tmdbId": tmdb_person_id}],
        }
        if len(works) == 1:
            result["work"] = works[0]
        else:
            result["works"] = works
        if ceremony == 5:
            result["note"] = "Tie under Academy rules at the time."
        results_by_ceremony[ceremony].append(result)
        people_latest[tmdb_person_id] = {
            "name": name,
            "tmdbPersonId": tmdb_person_id,
            "artworkAvailable": tmdb_person_id in artwork_ids,
        }

    if len(work_cache) != 100:
        raise RuntimeError(f"Expected 100 winning film identities, found {len(work_cache)}")

    for ceremony in sorted(EXPECTED_CEREMONIES):
        path = ceremony_file(ceremony)
        payload = json.loads(path.read_text(encoding="utf-8"))
        retained = [item for item in payload.get("results", []) if item.get("categoryId") != "best-actor"]
        payload["results"] = retained + results_by_ceremony[ceremony]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    people_output = {
        "schemaVersion": 1,
        "awardBodyId": "academy-awards",
        "categoryId": "best-actor",
        "status": "winner",
        "description": "Unique Best Actor winner identities derived from canonical ceremony results for Nuvio native PERSON sources.",
        "people": [
            {"name": item["name"], "tmdbPersonId": item["tmdbPersonId"]}
            for item in sorted(people_latest.values(), key=lambda value: (value["name"].casefold(), value["tmdbPersonId"]))
        ],
    }
    (GENERATED_DIR / "academy-best-actor-winners.people.json").write_text(
        json.dumps(people_output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    missing_artwork = [
        {"name": item["name"], "tmdbPersonId": item["tmdbPersonId"]}
        for item in sorted(people_latest.values(), key=lambda value: (value["name"].casefold(), value["tmdbPersonId"]))
        if not item["artworkAvailable"]
    ]
    report = {
        "categoryId": "best-actor",
        "uniqueWinnerCount": len(people_latest),
        "missingArtworkCount": len(missing_artwork),
        "missingArtwork": missing_artwork,
    }
    (REPORTS_DIR / "issue-4-best-actor-artwork-gaps.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Best Actor bootstrap complete: {len(winners)} winner records, {len(work_cache)} winning films, "
        f"{len(people_latest)} unique winners, {len(missing_artwork)} missing artwork identities."
    )


if __name__ == "__main__":
    main()
