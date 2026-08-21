#!/usr/bin/env python3
"""Generate and validate Academy Awards Best Supporting Actor winner outputs."""

from build_acting_category_outputs import ActingCategoryConfig, REPO_ROOT, run

CONFIG = ActingCategoryConfig(
    category_id="best-supporting-actor",
    display_name="Best Supporting Actor",
    catalogue_path=(
        REPO_ROOT
        / "catalog"
        / "movie"
        / "academy-best-supporting-actor-winning-films.json"
    ),
    people_path=(
        REPO_ROOT
        / "data"
        / "generated"
        / "academy-best-supporting-actor-winners.people.json"
    ),
    source_type="PERSON",
    expected_first_ceremony=9,
    expected_last_ceremony=98,
    expected_winner_results=90,
    expected_work_links=90,
    expected_unique_winners=81,
    command_name="scripts/build_best_supporting_actor_outputs.py",
)


if __name__ == "__main__":
    raise SystemExit(run(CONFIG))
