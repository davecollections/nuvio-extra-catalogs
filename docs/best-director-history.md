# Academy Awards Best Director history

Issue: #5

## Scope

This implementation records the Best Director winner relationship for every Academy Awards ceremony from the 1st ceremony in 1929 through the 98th ceremony in 2026. It generates:

- `catalog/movie/academy-best-director-winning-films.json`, containing 99 associated winning films; and
- `data/generated/academy-best-director-winners.people.json`, containing 77 unique winners keyed by TMDB Person ID for Nuvio native `DIRECTOR` sources.

The category is winner-only. Nominees and other directing categories are outside this implementation.

## Award authority and enrichment snapshots

The Academy Awards Database and official ceremony pages are authoritative for the winning directors and their credited films:

- https://awardsdatabase.oscars.org/
- https://www.oscars.org/oscars/ceremonies/2026

The initial structured import was cross-checked against `DLu/oscar_data` commit `c5e9716b7e020e70205d6b95f5a5678526c1b45f`. That dataset is derived from the Academy database and supplies IMDb identities; it is an enrichment and reconciliation source, not the award authority:

- https://github.com/DLu/oscar_data/commit/c5e9716b7e020e70205d6b95f5a5678526c1b45f

All 99 canonical winner results and film relationships match that pinned snapshot. Existing canonical title text was retained where an IMDb identity was already present, including `Dances with Wolves`. The canonical person spelling `Miloš Forman`, keyed by TMDB Person ID `3974`, is reused for both of his winning results.

TMDB IDs were resolved separately from award authority. Movie matches were accepted only when the resolved TMDB movie exposed the expected IMDb ID. Existing person identities were reused from `nuvio-people-assets`; missing identities were resolved through TMDB and retained by numeric TMDB Person ID.

The one-shot network reconciliation used to create the initial canonical records is intentionally not part of the production workflow. Canonical ceremony JSON is the durable source of truth, and generated outputs are deterministic and disposable.

## Historical edge cases

### 1st ceremony: two directing categories

The first ceremony had separate `Directing (Comedy Picture)` and `Directing (Dramatic Picture)` categories. Lewis Milestone won for *Two Arabian Knights* and Frank Borzage won for *7th Heaven*. The canonical ceremony therefore contains two explicit `best-director` winner results, each retaining a note with its historical category name.

### Joint credited winners

Three films have two credited winning directors. Each film remains one award result and one catalogue item, while both people are preserved on the canonical relationship:

- 34th ceremony: Robert Wise and Jerome Robbins for *West Side Story*;
- 80th ceremony: Joel Coen and Ethan Coen for *No Country for Old Men*; and
- 95th ceremony: Daniel Kwan and Daniel Scheinert for *Everything Everywhere All at Once*.

### Stable identity over display text

Repeated winners are deduplicated by TMDB Person ID, not by name text. The generator rejects one TMDB Person ID mapping to multiple canonical names so punctuation, diacritics, or spelling drift cannot silently create conflicting identities.

## Artwork coverage

Artwork coverage was compared with `davecollections/nuvio-people-assets` commit `3b2d945a1f340f7343023cc50875aecf79d5b355`.

- 77 unique Best Director winners
- 62 identities already covered
- 15 missing artwork identities

The missing identities are recorded in `reports/issue-5-best-director-artwork-gaps.json`. Artwork availability does not change canonical award results or block the movie catalogue. Cross-repository artwork additions remain Issue #6 work.

## Annual update process

For a new ceremony:

1. Verify the Best Director winner, all jointly credited winners, and the film against the Academy's official ceremony page or Awards Database.
2. Add one explicit `best-director` winner result to the new canonical ceremony file.
3. Reuse each winner's existing TMDB Person ID where available; resolve and manually verify any new person identity.
4. Resolve the movie's TMDB ID and retain its IMDb `tt` ID. Confirm the IDs refer to the same film.
5. Run `python scripts/build_best_director_outputs.py` to regenerate the movie and director outputs.
6. Run `python scripts/validate_awards_data.py` and every category generator in `--check` mode.
7. Recheck People artwork coverage separately and update the dated artwork-gap report when needed.
8. Test the changed manifest and catalogue in Nuvio before release.

The shared acquisition, identity-matching, ambiguity, correction, and audit policy is defined in [`awards-source-strategy.md`](awards-source-strategy.md).

## Generator validation

The generator enforces:

- ceremonies 1 through 98 with filename number/year agreement;
- 99 winner results, including both 1st-ceremony historical category winners;
- 99 unique winning-film IMDb and TMDB relationships;
- 102 director links and 77 unique positive TMDB Person IDs;
- exactly two credited people only for the 34th, 80th, and 95th ceremonies;
- one canonical name per TMDB Person ID;
- exactly one movie work per result with a release year;
- valid Stremio movie Meta Preview output, newest ceremony first; and
- reproducible movie and director outputs in `--check` mode.
