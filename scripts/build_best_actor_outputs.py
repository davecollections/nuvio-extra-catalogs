#!/usr/bin/env python3
"""Generate and validate Academy Awards Best Actor winner outputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "data" / "awards" / "academy-awards" / "results"
CATALOGUE_PATH = REPO_ROOT / "catalog" / "movie" / "academy-best-actor-winning-films.json"
PEOPLE_PATH = REPO_ROOT / "data" / "generated" / "academy-best-actor-winners.people.json"
FILE_RE = re.compile(r"^(?P<number>\d{3})-(?P<year>\d{4})\.json$")
IMDB_RE = re.compile(r"^tt\d+$")
POSTER_TEMPLATE = "https://images.metahub.space/poster/medium/{imdb_id}/img"
EXPECTED_LAST_CEREMONY = 98
EXPECTED_WINNER_RESULTS = 99
EXPECTED_WORK_LINKS = 100
EXPECTED_UNIQUE_WINNERS = 87


class ValidationError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc


def validate_work(path: Path, work: object) -> dict:
    if not isinstance(work, dict) or work.get("mediaType") != "movie":
        raise ValidationError(f"{path}: Best Actor winner work must be a movie")

    title = work.get("title")
    tmdb_id = work.get("tmdbId")
    imdb_id = work.get("imdbId")
    release_year = work.get("releaseYear")

    if not isinstance(title, str) or not title.strip():
        raise ValidationError(f"{path}: Best Actor winning work is missing a title")
    if not isinstance(tmdb_id, int) or isinstance(tmdb_id, bool) or tmdb_id < 1:
        raise ValidationError(f"{path}: {title!r} has invalid or missing TMDB movie ID")
    if not isinstance(imdb_id, str) or not IMDB_RE.fullmatch(imdb_id):
        raise ValidationError(f"{path}: {title!r} has invalid or missing IMDb ID")
    if release_year is not None and (
        not isinstance(release_year, int)
        or isinstance(release_year, bool)
        or not 1800 <= release_year <= 2200
    ):
        raise ValidationError(f"{path}: {title!r} has invalid releaseYear")

    return {
        "title": title.strip(),
        "tmdbId": tmdb_id,
        "imdbId": imdb_id,
        "releaseYear": release_year,
    }


def validate_person(path: Path, result: dict) -> dict:
    people = result.get("people")
    if not isinstance(people, list) or len(people) != 1 or not isinstance(people[0], dict):
        raise ValidationError(f"{path}: Best Actor winner must contain exactly one person")

    person = people[0]
    name = person.get("name")
    tmdb_id = person.get("tmdbId")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError(f"{path}: Best Actor winner is missing a person name")
    if not isinstance(tmdb_id, int) or isinstance(tmdb_id, bool) or tmdb_id < 1:
        raise ValidationError(f"{path}: {name!r} has invalid or missing TMDB Person ID")
    return {"name": name.strip(), "tmdbPersonId": tmdb_id}


def collect_outputs() -> tuple[list[dict], list[dict]]:
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        raise ValidationError(f"No ceremony files found under {RESULTS_DIR}")

    seen_numbers: set[int] = set()
    seen_imdb: set[str] = set()
    people_by_id: dict[int, str] = {}
    catalogue_rows: list[dict] = []
    winner_result_count = 0
    work_link_count = 0

    for path in files:
        match = FILE_RE.fullmatch(path.name)
        if not match:
            raise ValidationError(
                f"{path}: expected filename NNN-YYYY.json using ceremony number and ceremony year"
            )

        expected_number = int(match.group("number"))
        expected_year = int(match.group("year"))
        data = load_json(path)

        if data.get("awardBodyId") != "academy-awards":
            raise ValidationError(f"{path}: awardBodyId must be academy-awards")
        ceremony = data.get("ceremony")
        if not isinstance(ceremony, dict):
            raise ValidationError(f"{path}: missing ceremony object")
        number = ceremony.get("number")
        year = ceremony.get("year")
        if number != expected_number or year != expected_year:
            raise ValidationError(
                f"{path}: filename ceremony {expected_number}/{expected_year} does not match data {number}/{year}"
            )
        if number in seen_numbers:
            raise ValidationError(f"{path}: duplicate ceremony number {number}")
        seen_numbers.add(number)

        results = data.get("results")
        if not isinstance(results, list):
            raise ValidationError(f"{path}: results must be an array")
        winners = [
            result
            for result in results
            if isinstance(result, dict)
            and result.get("categoryId") == "best-actor"
            and result.get("status") == "winner"
        ]

        expected_count = 2 if number == 5 else 1
        if len(winners) != expected_count:
            raise ValidationError(
                f"{path}: expected {expected_count} Best Actor winner result(s), found {len(winners)}"
            )

        for result_index, result in enumerate(winners):
            winner_result_count += 1
            person = validate_person(path, result)
            person_id = person["tmdbPersonId"]
            existing_name = people_by_id.get(person_id)
            if existing_name is not None and existing_name != person["name"]:
                raise ValidationError(
                    f"{path}: TMDB Person ID {person_id} maps to both {existing_name!r} and {person['name']!r}"
                )
            people_by_id[person_id] = person["name"]

            has_work = "work" in result
            has_works = "works" in result
            if has_work == has_works:
                raise ValidationError(f"{path}: Best Actor winner must contain exactly one of work or works")

            if has_works:
                raw_works = result.get("works")
                if not isinstance(raw_works, list) or not raw_works:
                    raise ValidationError(f"{path}: works must be a non-empty array")
                if number != 1 or len(raw_works) != 2:
                    raise ValidationError(
                        f"{path}: multi-work Best Actor result is only expected for the 1st ceremony with two works"
                    )
            else:
                raw_works = [result.get("work")]

            for work_index, raw_work in enumerate(raw_works):
                work = validate_work(path, raw_work)
                work_link_count += 1
                imdb_id = work["imdbId"]
                if imdb_id in seen_imdb:
                    raise ValidationError(f"{path}: duplicate Best Actor winning-film IMDb ID {imdb_id}")
                seen_imdb.add(imdb_id)
                catalogue_rows.append(
                    {
                        "ceremonyNumber": number,
                        "resultIndex": result_index,
                        "workIndex": work_index,
                        "meta": {
                            "id": imdb_id,
                            "type": "movie",
                            "name": work["title"],
                            "poster": POSTER_TEMPLATE.format(imdb_id=imdb_id),
                            "posterShape": "poster",
                        },
                    }
                )

    expected_numbers = list(range(1, EXPECTED_LAST_CEREMONY + 1))
    if sorted(seen_numbers) != expected_numbers:
        missing = sorted(set(expected_numbers) - seen_numbers)
        extra = sorted(seen_numbers - set(expected_numbers))
        raise ValidationError(f"Ceremony coverage mismatch; missing={missing}, extra={extra}")
    if winner_result_count != EXPECTED_WINNER_RESULTS:
        raise ValidationError(
            f"Expected {EXPECTED_WINNER_RESULTS} Best Actor winner results, found {winner_result_count}"
        )
    if work_link_count != EXPECTED_WORK_LINKS:
        raise ValidationError(f"Expected {EXPECTED_WORK_LINKS} winning-film links, found {work_link_count}")
    if len(people_by_id) != EXPECTED_UNIQUE_WINNERS:
        raise ValidationError(
            f"Expected {EXPECTED_UNIQUE_WINNERS} unique Best Actor winners, found {len(people_by_id)}"
        )

    catalogue_rows.sort(
        key=lambda row: (-row["ceremonyNumber"], row["resultIndex"], row["workIndex"])
    )
    people = [
        {"name": name, "tmdbPersonId": person_id}
        for person_id, name in people_by_id.items()
    ]
    people.sort(key=lambda item: (item["name"].casefold(), item["tmdbPersonId"]))
    return [row["meta"] for row in catalogue_rows], people


def render_catalogue(metas: list[dict]) -> str:
    return json.dumps({"metas": metas}, ensure_ascii=False, separators=(",", ":")) + "\n"


def render_people(people: list[dict]) -> str:
    payload = {
        "schemaVersion": 1,
        "awardBodyId": "academy-awards",
        "categoryId": "best-actor",
        "status": "winner",
        "description": (
            "Unique Best Actor winner identities derived from canonical ceremony results "
            "for Nuvio native PERSON sources."
        ),
        "people": people,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def check_output(path: Path, expected: str, label: str) -> None:
    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"could not read {path}: {exc}") from exc
    if current != expected:
        raise ValidationError(f"{label} is out of date; run scripts/build_best_actor_outputs.py")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate canonical Best Actor data and fail if either generated output is out of date.",
    )
    args = parser.parse_args()

    try:
        metas, people = collect_outputs()
        catalogue = render_catalogue(metas)
        person_output = render_people(people)
        if args.check:
            check_output(CATALOGUE_PATH, catalogue, "Best Actor movie catalogue")
            check_output(PEOPLE_PATH, person_output, "Best Actor person output")
            print(
                "Best Actor data and generated outputs are valid: "
                f"{EXPECTED_LAST_CEREMONY} ceremonies, {len(metas)} films, {len(people)} unique winners."
            )
            return 0

        CATALOGUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PEOPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CATALOGUE_PATH.write_text(catalogue, encoding="utf-8")
        PEOPLE_PATH.write_text(person_output, encoding="utf-8")
        print(f"Wrote {CATALOGUE_PATH} with {len(metas)} films.")
        print(f"Wrote {PEOPLE_PATH} with {len(people)} unique winners.")
        return 0
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
