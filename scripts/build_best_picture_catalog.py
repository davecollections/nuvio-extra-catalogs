#!/usr/bin/env python3
"""Generate and validate the Academy Awards Best Picture winners catalogue."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "data" / "awards" / "academy-awards" / "results"
OUTPUT_PATH = REPO_ROOT / "catalog" / "movie" / "academy-best-picture-winners.json"
FILE_RE = re.compile(r"^(?P<number>\d{3})-(?P<year>\d{4})\.json$")
IMDB_RE = re.compile(r"^tt\d+$")
POSTER_TEMPLATE = "https://images.metahub.space/poster/medium/{imdb_id}/img"


class ValidationError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc


def collect_winners() -> list[dict]:
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        raise ValidationError(f"No ceremony files found under {RESULTS_DIR}")

    winners: list[dict] = []
    seen_numbers: set[int] = set()
    seen_imdb: set[str] = set()

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

        matches = [
            result
            for result in results
            if isinstance(result, dict)
            and result.get("categoryId") == "best-picture"
            and result.get("status") == "winner"
        ]
        if len(matches) != 1:
            raise ValidationError(
                f"{path}: expected exactly one best-picture winner, found {len(matches)}"
            )

        work = matches[0].get("work")
        if not isinstance(work, dict) or work.get("mediaType") != "movie":
            raise ValidationError(f"{path}: Best Picture winner must contain a movie work")

        title = work.get("title")
        imdb_id = work.get("imdbId")
        if not isinstance(title, str) or not title.strip():
            raise ValidationError(f"{path}: winner is missing a title")
        if not isinstance(imdb_id, str) or not IMDB_RE.fullmatch(imdb_id):
            raise ValidationError(f"{path}: winner has invalid or missing IMDb ID")
        if imdb_id in seen_imdb:
            raise ValidationError(f"{path}: duplicate IMDb ID {imdb_id}")
        seen_imdb.add(imdb_id)

        poster = POSTER_TEMPLATE.format(imdb_id=imdb_id)
        if not poster:
            raise ValidationError(f"{path}: winner is missing a poster URL")

        winners.append(
            {
                "ceremonyNumber": number,
                "ceremonyYear": year,
                "meta": {
                    "id": imdb_id,
                    "type": "movie",
                    "name": title.strip(),
                    "poster": poster,
                    "posterShape": "poster",
                },
            }
        )

    ordered_numbers = sorted(seen_numbers)
    expected_numbers = list(range(1, max(ordered_numbers) + 1))
    if ordered_numbers != expected_numbers:
        missing = sorted(set(expected_numbers) - seen_numbers)
        raise ValidationError(f"Missing ceremony files: {missing}")

    return sorted(winners, key=lambda item: item["ceremonyNumber"], reverse=True)


def render_catalogue() -> str:
    winners = collect_winners()
    payload = {"metas": [winner["meta"] for winner in winners]}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate source data and fail if the generated catalogue is out of date.",
    )
    args = parser.parse_args()

    try:
        rendered = render_catalogue()
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.check:
        try:
            current = OUTPUT_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: could not read {OUTPUT_PATH}: {exc}", file=sys.stderr)
            return 1
        if current != rendered:
            print(
                "ERROR: Best Picture catalogue is out of date. "
                "Run scripts/build_best_picture_catalog.py.",
                file=sys.stderr,
            )
            return 1
        print("Best Picture data and generated catalogue are valid.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} from {len(json.loads(rendered)['metas'])} ceremonies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
