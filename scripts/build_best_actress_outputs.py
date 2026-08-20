#!/usr/bin/env python3
"""Generate and validate Academy Awards Best Actress winner outputs."""

from build_acting_category_outputs import ActingCategoryConfig, REPO_ROOT, run

CONFIG = ActingCategoryConfig(
    category_id="best-actress",
    display_name="Best Actress",
    catalogue_path=REPO_ROOT / "catalog" / "movie" / "academy-best-actress-winning-films.json",
    people_path=REPO_ROOT / "data" / "generated" / "academy-best-actress-winners.people.json",
    source_type="PERSON",
    expected_last_ceremony=98,
    expected_winner_results=99,
    expected_work_links=101,
    expected_unique_winners=81,
    command_name="scripts/build_best_actress_outputs.py",
    winner_counts={41: 2},
    multi_work_counts={1: 3},
)


if __name__ == "__main__":
    raise SystemExit(run(CONFIG))
