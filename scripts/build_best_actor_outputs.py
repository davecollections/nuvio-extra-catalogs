#!/usr/bin/env python3
"""Generate and validate Academy Awards Best Actor winner outputs."""

from build_acting_category_outputs import ActingCategoryConfig, REPO_ROOT, run

CONFIG = ActingCategoryConfig(
    category_id="best-actor",
    display_name="Best Actor",
    catalogue_path=REPO_ROOT / "catalog" / "movie" / "academy-best-actor-winning-films.json",
    people_path=REPO_ROOT / "data" / "generated" / "academy-best-actor-winners.people.json",
    source_type="PERSON",
    expected_last_ceremony=98,
    expected_winner_results=99,
    expected_work_links=100,
    expected_unique_winners=87,
    command_name="scripts/build_best_actor_outputs.py",
    winner_counts={5: 2},
    multi_work_counts={1: 2},
)


if __name__ == "__main__":
    raise SystemExit(run(CONFIG))
