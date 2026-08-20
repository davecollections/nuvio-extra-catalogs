#!/usr/bin/env python3
"""Shared generator and validator for Academy Awards acting winner outputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "data" / "awards" / "academy-awards" / "results"
FILE_RE = re.compile(r"^(?P<number>\d{3})-(?P<year>\d{4})\.json$")
IMDB_RE = re.compile(r"^tt\d+$")
POSTER_TEMPLATE = "https://images.metahub.space/poster/medium/{imdb_id}/img"


class ValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActingCategoryConfig:
    category_id: str
    display_name: str
    catalogue_path: Path
    people_path: Path
    source_type: str
    expected_last_ceremony: int
    expected_winner_results: int
    expected_work_links: int
    expected_unique_winners: int
    command_name: str
    winner_counts: dict[int, int] = field(default_factory=dict)
    multi_work_counts: dict[int, int] = field(default_factory=dict)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected a JSON object")
    return value


def validate_work(path: Path, raw_work: object, display_name: str) -> dict:
    if not isinstance(raw_work, dict) or raw_work.get("mediaType") != "movie":
        raise ValidationError(f"{path}: {display_name} winner work must be a movie")

    title = raw_work.get("title")
    tmdb_id = raw_work.get("tmdbId")
    imdb_id = raw_work.get("imdbId")
    release_year = raw_work.get("releaseYear")
    if not isinstance(title, str) or not title.strip():
        raise ValidationError(f"{path}: {display_name} winning work is missing a title")
    if not isinstance(tmdb_id, int) or isinstance(tmdb_id, bool) or tmdb_id < 1:
        raise ValidationError(f"{path}: {title!r} has invalid or missing TMDB movie ID")
    if not isinstance(imdb_id, str) or not IMDB_RE.fullmatch(imdb_id):
        raise ValidationError(f"{path}: {title!r} has invalid or missing IMDb ID")
    if (
        not isinstance(release_year, int)
        or isinstance(release_year, bool)
        or not 1800 <= release_year <= 2200
    ):
        raise ValidationError(f"{path}: {title!r} has invalid or missing releaseYear")
    return {
        "title": title.strip(),
        "tmdbId": tmdb_id,
        "imdbId": imdb_id,
        "releaseYear": release_year,
    }


def validate_person(path: Path, result: dict, display_name: str) -> dict:
    people = result.get("people")
    if not isinstance(people, list) or len(people) != 1 or not isinstance(people[0], dict):
        raise ValidationError(f"{path}: {display_name} winner must contain exactly one person")
    person = people[0]
    name = person.get("name")
    tmdb_id = person.get("tmdbId")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError(f"{path}: {display_name} winner is missing a person name")
    if not isinstance(tmdb_id, int) or isinstance(tmdb_id, bool) or tmdb_id < 1:
        raise ValidationError(f"{path}: {name!r} has invalid or missing TMDB Person ID")
    return {"name": name.strip(), "tmdbPersonId": tmdb_id}


def collect_outputs(config: ActingCategoryConfig) -> tuple[list[dict], list[dict]]:
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
                f"{path}: filename ceremony {expected_number}/{expected_year} "
                f"does not match data {number}/{year}"
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
            and result.get("categoryId") == config.category_id
            and result.get("status") == "winner"
        ]
        expected_count = config.winner_counts.get(number, 1)
        if len(winners) != expected_count:
            raise ValidationError(
                f"{path}: expected {expected_count} {config.display_name} winner result(s), "
                f"found {len(winners)}"
            )

        for result_index, result in enumerate(winners):
            winner_result_count += 1
            person = validate_person(path, result, config.display_name)
            person_id = person["tmdbPersonId"]
            existing_name = people_by_id.get(person_id)
            if existing_name is not None and existing_name != person["name"]:
                raise ValidationError(
                    f"{path}: TMDB Person ID {person_id} maps to both "
                    f"{existing_name!r} and {person['name']!r}"
                )
            people_by_id[person_id] = person["name"]

            has_work = "work" in result
            has_works = "works" in result
            if has_work == has_works:
                raise ValidationError(
                    f"{path}: {config.display_name} winner must contain exactly one of work or works"
                )
            expected_multi_count = config.multi_work_counts.get(number)
            if has_works:
                raw_works = result.get("works")
                if not isinstance(raw_works, list) or not raw_works:
                    raise ValidationError(f"{path}: works must be a non-empty array")
                if expected_multi_count is None or len(raw_works) != expected_multi_count:
                    raise ValidationError(
                        f"{path}: unexpected {config.display_name} multi-work result; "
                        f"configured count is {expected_multi_count}"
                    )
            else:
                if expected_multi_count is not None:
                    raise ValidationError(
                        f"{path}: expected {expected_multi_count} works for {config.display_name}"
                    )
                raw_works = [result.get("work")]

            for work_index, raw_work in enumerate(raw_works):
                work = validate_work(path, raw_work, config.display_name)
                work_link_count += 1
                imdb_id = work["imdbId"]
                if imdb_id in seen_imdb:
                    raise ValidationError(
                        f"{path}: duplicate {config.display_name} winning-film IMDb ID {imdb_id}"
                    )
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

    expected_numbers = list(range(1, config.expected_last_ceremony + 1))
    if sorted(seen_numbers) != expected_numbers:
        missing = sorted(set(expected_numbers) - seen_numbers)
        extra = sorted(seen_numbers - set(expected_numbers))
        raise ValidationError(f"Ceremony coverage mismatch; missing={missing}, extra={extra}")
    if winner_result_count != config.expected_winner_results:
        raise ValidationError(
            f"Expected {config.expected_winner_results} {config.display_name} winner results, "
            f"found {winner_result_count}"
        )
    if work_link_count != config.expected_work_links:
        raise ValidationError(
            f"Expected {config.expected_work_links} winning-film links, found {work_link_count}"
        )
    if len(people_by_id) != config.expected_unique_winners:
        raise ValidationError(
            f"Expected {config.expected_unique_winners} unique {config.display_name} winners, "
            f"found {len(people_by_id)}"
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


def render_people(config: ActingCategoryConfig, people: list[dict]) -> str:
    payload = {
        "schemaVersion": 1,
        "awardBodyId": "academy-awards",
        "categoryId": config.category_id,
        "status": "winner",
        "description": (
            f"Unique {config.display_name} winner identities derived from canonical ceremony "
            f"results for Nuvio native {config.source_type} sources."
        ),
        "people": people,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def check_output(path: Path, expected: str, label: str, command_name: str) -> None:
    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"could not read {path}: {exc}") from exc
    if current != expected:
        raise ValidationError(f"{label} is out of date; run {command_name}")


def run(config: ActingCategoryConfig, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            f"Validate canonical {config.display_name} data and fail if either generated "
            "output is out of date."
        ),
    )
    args = parser.parse_args(argv)
    try:
        metas, people = collect_outputs(config)
        catalogue = render_catalogue(metas)
        person_output = render_people(config, people)
        if args.check:
            check_output(
                config.catalogue_path,
                catalogue,
                f"{config.display_name} movie catalogue",
                config.command_name,
            )
            check_output(
                config.people_path,
                person_output,
                f"{config.display_name} person output",
                config.command_name,
            )
            print(
                f"{config.display_name} data and generated outputs are valid: "
                f"{config.expected_last_ceremony} ceremonies, {len(metas)} films, "
                f"{len(people)} unique winners."
            )
            return 0

        config.catalogue_path.parent.mkdir(parents=True, exist_ok=True)
        config.people_path.parent.mkdir(parents=True, exist_ok=True)
        config.catalogue_path.write_text(catalogue, encoding="utf-8")
        config.people_path.write_text(person_output, encoding="utf-8")
        print(f"Wrote {config.catalogue_path} with {len(metas)} films.")
        print(f"Wrote {config.people_path} with {len(people)} unique winners.")
        return 0
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
