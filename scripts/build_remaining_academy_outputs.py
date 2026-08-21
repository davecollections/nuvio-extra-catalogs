#!/usr/bin/env python3
"""Generate and validate the 18 Academy winner-film catalogues added by Issue #24."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "data" / "awards" / "academy-awards" / "results"
CATALOGUE_DIR = REPO_ROOT / "catalog" / "movie"
FILE_RE = re.compile(r"^(?P<number>\d{3})-(?P<year>\d{4})\.json$")
IMDB_TITLE_RE = re.compile(r"^tt\d+$")
IMDB_PERSON_RE = re.compile(r"^nm\d+$")
POSTER_TEMPLATE = "https://images.metahub.space/poster/medium/{imdb_id}/img"


class ValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CategoryContract:
    category_id: str
    display_name: str
    catalogue_id: str
    first_ceremony: int
    last_ceremony: int
    expected_results: int
    expected_work_links: int
    expected_catalogue_items: int
    expected_person_links: int
    expected_unique_imdb_people: int
    expected_unique_tmdb_people: int
    expected_unresolved_tmdb_people: int
    missing_ceremonies: frozenset[int] = frozenset()
    result_count_overrides: dict[int, int] = field(default_factory=dict)
    no_work_ceremonies: frozenset[int] = frozenset()

    @property
    def catalogue_path(self) -> Path:
        return CATALOGUE_DIR / f"{self.catalogue_id}.json"


def count_overrides(numbers: set[int], *, special: dict[int, int] | None = None) -> dict[int, int]:
    values = {number: 2 for number in numbers}
    if special:
        values.update(special)
    return values


CONTRACTS = (
    CategoryContract("animated-feature-film", "Animated Feature Film", "academy-animated-feature-film-winning-films", 74, 98, 25, 25, 25, 54, 45, 44, 1),
    CategoryContract("animated-short-film", "Animated Short Film", "academy-animated-short-film-winning-films", 5, 98, 94, 94, 94, 120, 92, 87, 5),
    CategoryContract("casting", "Casting", "academy-casting-winning-films", 98, 98, 1, 1, 1, 1, 1, 1, 0),
    CategoryContract(
        "cinematography", "Cinematography", "academy-cinematography-winning-films",
        1, 98, 125, 125, 125, 141, 104, 104, 0,
        result_count_overrides=count_overrides(set(range(12, 30)) | set(range(31, 40))),
    ),
    CategoryContract(
        "costume-design", "Costume Design", "academy-costume-design-winning-films",
        21, 98, 95, 95, 95, 119, 73, 71, 2,
        result_count_overrides=count_overrides(set(range(21, 30)) | set(range(32, 40))),
    ),
    CategoryContract(
        "documentary-feature-film", "Documentary Feature Film", "academy-documentary-feature-film-winning-films",
        15, 98, 87, 87, 87, 144, 136, 132, 4,
        missing_ceremonies=frozenset({19}),
        result_count_overrides={15: 4, 59: 2},
    ),
    CategoryContract(
        "documentary-short-film", "Documentary Short Film", "academy-documentary-short-film-winning-films",
        14, 98, 84, 84, 84, 115, 107, 93, 14,
        missing_ceremonies=frozenset({15, 30}),
        result_count_overrides={22: 2},
    ),
    CategoryContract("film-editing", "Film Editing", "academy-film-editing-winning-films", 7, 98, 92, 92, 92, 121, 100, 100, 0),
    CategoryContract(
        "international-feature-film", "International Feature Film", "academy-international-feature-film-winning-films",
        23, 98, 75, 75, 75, 2, 2, 2, 0,
        missing_ceremonies=frozenset({26}),
    ),
    CategoryContract(
        "live-action-short-film", "Live Action Short Film", "academy-live-action-short-film-winning-films",
        30, 98, 71, 71, 71, 108, 106, 93, 13,
        result_count_overrides={67: 2, 98: 2},
    ),
    CategoryContract(
        "makeup-and-hairstyling", "Makeup and Hairstyling", "academy-makeup-and-hairstyling-winning-films",
        54, 98, 44, 44, 44, 102, 84, 79, 5,
        missing_ceremonies=frozenset({56}),
    ),
    CategoryContract(
        "original-score", "Music (Original Score)", "academy-original-score-winning-films",
        11, 98, 87, 87, 87, 98, 73, 70, 3,
        missing_ceremonies=frozenset({30}),
    ),
    CategoryContract("original-song", "Music (Original Song)", "academy-original-song-winning-films", 7, 98, 92, 92, 92, 183, 141, 128, 13),
    CategoryContract(
        "production-design", "Production Design", "academy-production-design-winning-films",
        1, 98, 123, 124, 124, 312, 203, 195, 8,
        result_count_overrides=count_overrides(set(range(13, 30)) | set(range(32, 40))),
    ),
    CategoryContract(
        "sound", "Sound", "academy-sound-winning-films",
        3, 98, 138, 136, 118, 300, 195, 182, 13,
        result_count_overrides=count_overrides(
            {36, 37, 38, 39, 40, 55, 56, 58, 59} | set(range(61, 93)),
            special={85: 3},
        ),
        no_work_ceremonies=frozenset({4, 5}),
    ),
    CategoryContract(
        "visual-effects", "Visual Effects", "academy-visual-effects-winning-films",
        1, 98, 79, 79, 79, 237, 171, 156, 15,
        missing_ceremonies=frozenset({2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 45, 46, 47, 48, 49, 51, 53, 56, 63}),
    ),
    CategoryContract("adapted-screenplay", "Writing (Adapted Screenplay)", "academy-adapted-screenplay-winning-films", 1, 98, 98, 98, 98, 137, 127, 124, 3),
    CategoryContract(
        "original-screenplay", "Writing (Original Screenplay)", "academy-original-screenplay-winning-films",
        13, 98, 85, 85, 85, 126, 120, 120, 0,
        missing_ceremonies=frozenset({21}),
    ),
)


def load_ceremonies() -> list[tuple[Path, int, list[dict]]]:
    files = sorted(RESULTS_DIR.glob("*.json"))
    if len(files) != 98:
        raise ValidationError(f"expected 98 ceremony files, found {len(files)}")
    ceremonies: list[tuple[Path, int, list[dict]]] = []
    for path in files:
        match = FILE_RE.fullmatch(path.name)
        if not match:
            raise ValidationError(f"{path}: invalid ceremony filename")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"{path}: invalid JSON: {exc}") from exc
        number = payload.get("ceremony", {}).get("number")
        if number != int(match.group("number")):
            raise ValidationError(f"{path}: ceremony number does not match filename")
        results = payload.get("results")
        if not isinstance(results, list):
            raise ValidationError(f"{path}: results must be an array")
        ceremonies.append((path, number, results))
    return ceremonies


def collect_category(
    contract: CategoryContract, ceremonies: list[tuple[Path, int, list[dict]]]
) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    result_count = 0
    work_link_count = 0
    person_link_count = 0
    imdb_people: dict[str, str] = {}
    tmdb_people: dict[int, str] = {}
    unresolved_imdb_people: set[str] = set()

    for path, ceremony_number, results in ceremonies:
        winners = [
            result
            for result in results
            if isinstance(result, dict)
            and result.get("categoryId") == contract.category_id
            and result.get("status") == "winner"
        ]
        if ceremony_number < contract.first_ceremony or ceremony_number > contract.last_ceremony:
            expected_count = 0
        elif ceremony_number in contract.missing_ceremonies:
            expected_count = 0
        else:
            expected_count = contract.result_count_overrides.get(ceremony_number, 1)
        if len(winners) != expected_count:
            raise ValidationError(
                f"{path}: expected {expected_count} {contract.display_name} winner result(s), "
                f"found {len(winners)}"
            )

        no_work_results = 0
        for result_index, result in enumerate(winners):
            result_count += 1
            raw_works = result.get("works") or ([result["work"]] if "work" in result else [])
            if not raw_works:
                no_work_results += 1
            for work_index, work in enumerate(raw_works):
                if not isinstance(work, dict) or work.get("mediaType") != "movie":
                    raise ValidationError(f"{path}: {contract.display_name} work must be a movie")
                title = work.get("title")
                imdb_id = work.get("imdbId")
                if not isinstance(title, str) or not title.strip():
                    raise ValidationError(f"{path}: {contract.display_name} work is missing a title")
                if not isinstance(imdb_id, str) or not IMDB_TITLE_RE.fullmatch(imdb_id):
                    raise ValidationError(f"{path}: {title!r} is missing a valid IMDb title ID")
                work_link_count += 1
                rows.append(
                    {
                        "ceremony": ceremony_number,
                        "resultIndex": result_index,
                        "workIndex": work_index,
                        "imdbId": imdb_id,
                        "title": title.strip(),
                    }
                )

            people = result.get("people", [])
            if not isinstance(people, list):
                raise ValidationError(f"{path}: people must be an array")
            person_link_count += len(people)
            for person in people:
                if not isinstance(person, dict) or not isinstance(person.get("name"), str):
                    raise ValidationError(f"{path}: invalid person relationship")
                name = person["name"].strip()
                imdb_id = person.get("imdbId")
                tmdb_id = person.get("tmdbId")
                if imdb_id is not None:
                    if not isinstance(imdb_id, str) or not IMDB_PERSON_RE.fullmatch(imdb_id):
                        raise ValidationError(f"{path}: {name!r} has an invalid IMDb Person ID")
                    previous = imdb_people.get(imdb_id)
                    if previous is not None and previous != name:
                        raise ValidationError(
                            f"{path}: IMDb Person ID {imdb_id} maps to {previous!r} and {name!r}"
                        )
                    imdb_people[imdb_id] = name
                    if tmdb_id is None:
                        unresolved_imdb_people.add(imdb_id)
                if tmdb_id is not None:
                    if not isinstance(tmdb_id, int) or isinstance(tmdb_id, bool) or tmdb_id < 1:
                        raise ValidationError(f"{path}: {name!r} has an invalid TMDB Person ID")
                    previous = tmdb_people.get(tmdb_id)
                    if previous is not None and previous != name:
                        raise ValidationError(
                            f"{path}: TMDB Person ID {tmdb_id} maps to {previous!r} and {name!r}"
                        )
                    tmdb_people[tmdb_id] = name
        expected_no_work = 1 if ceremony_number in contract.no_work_ceremonies else 0
        if no_work_results != expected_no_work:
            raise ValidationError(
                f"{path}: expected {expected_no_work} non-film {contract.display_name} result(s), "
                f"found {no_work_results}"
            )

    actuals = {
        "results": result_count,
        "workLinks": work_link_count,
        "personLinks": person_link_count,
        "uniqueImdbPeople": len(imdb_people),
        "uniqueTmdbPeople": len(tmdb_people),
        "unresolvedTmdbPeople": len(unresolved_imdb_people),
    }
    expected = {
        "results": contract.expected_results,
        "workLinks": contract.expected_work_links,
        "personLinks": contract.expected_person_links,
        "uniqueImdbPeople": contract.expected_unique_imdb_people,
        "uniqueTmdbPeople": contract.expected_unique_tmdb_people,
        "unresolvedTmdbPeople": contract.expected_unresolved_tmdb_people,
    }
    if actuals != expected:
        raise ValidationError(
            f"{contract.display_name} contract mismatch; expected={expected}, actual={actuals}"
        )

    rows.sort(key=lambda row: (-row["ceremony"], row["resultIndex"], row["workIndex"]))
    seen_imdb: set[str] = set()
    metas: list[dict] = []
    for row in rows:
        if row["imdbId"] in seen_imdb:
            continue
        seen_imdb.add(row["imdbId"])
        metas.append(
            {
                "id": row["imdbId"],
                "type": "movie",
                "name": row["title"],
                "poster": POSTER_TEMPLATE.format(imdb_id=row["imdbId"]),
                "posterShape": "poster",
            }
        )
    if len(metas) != contract.expected_catalogue_items:
        raise ValidationError(
            f"{contract.display_name}: expected {contract.expected_catalogue_items} unique "
            f"catalogue films, found {len(metas)}"
        )
    return metas, actuals


def render_catalogue(metas: list[dict]) -> str:
    return json.dumps({"metas": metas}, ensure_ascii=False, separators=(",", ":")) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        ceremonies = load_ceremonies()
        summaries: list[str] = []
        for contract in CONTRACTS:
            metas, actuals = collect_category(contract, ceremonies)
            rendered = render_catalogue(metas)
            if args.check:
                try:
                    current = contract.catalogue_path.read_text(encoding="utf-8")
                except OSError as exc:
                    raise ValidationError(f"could not read {contract.catalogue_path}: {exc}") from exc
                if current != rendered:
                    raise ValidationError(
                        f"{contract.display_name} catalogue is out of date; run "
                        "scripts/build_remaining_academy_outputs.py"
                    )
            else:
                contract.catalogue_path.parent.mkdir(parents=True, exist_ok=True)
                contract.catalogue_path.write_text(rendered, encoding="utf-8")
            summaries.append(
                f"{contract.category_id}={len(metas)} films/{actuals['results']} results"
            )
        verb = "valid" if args.check else "written"
        print(f"Remaining Academy outputs are {verb}: " + "; ".join(summaries) + ".")
        return 0
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
