# Academy Awards Best Actor history

Issue: #4

## Scope

This implementation records the Best Actor winner relationship for every Academy Awards ceremony from the 1st ceremony in 1929 through the 98th ceremony in 2026. It generates:

- `catalog/movie/academy-best-actor-winning-films.json`, containing the 100 associated winning films; and
- `data/generated/academy-best-actor-winners.people.json`, containing 87 unique winners keyed by TMDB Person ID.

The category is winner-only. Nominees and the remaining acting categories are outside this implementation.

## Award authority and enrichment snapshots

The Academy Awards Database and official ceremony pages are authoritative for who won and which work received the acting recognition:

- https://awardsdatabase.oscars.org/
- https://www.oscars.org/oscars/ceremonies/2026

The initial structured import was cross-checked against `DLu/oscar_data` commit `c5e9716b7e020e70205d6b95f5a5678526c1b45f`. That dataset is derived from the Academy database and supplies IMDb identities; it is an enrichment and reconciliation source, not the award authority:

- https://github.com/DLu/oscar_data/commit/c5e9716b7e020e70205d6b95f5a5678526c1b45f

All 99 canonical winner results and their IMDb film relationships match that pinned snapshot. The only deliberate text normalization is `Daniel Day-Lewis`, keyed consistently by TMDB Person ID `11856`.

TMDB IDs were resolved separately from award authority. Movie matches were accepted only when the resolved TMDB movie exposed the expected IMDb ID. Existing person identities were reused from `nuvio-people-assets`; missing identities were resolved through TMDB and retained by numeric TMDB Person ID.

The one-shot network bootstrap used to create the initial canonical records is intentionally not part of the production workflow. Canonical ceremony JSON is the durable source of truth, and generated outputs are deterministic and disposable.

## Historical edge cases

### 1st ceremony: one award, two films

The Academy records Emil Jannings as the Best Actor winner for both *The Last Command* and *The Way of All Flesh*. The canonical result therefore uses one person and a `works` array containing both films. The movie catalogue deliberately emits two Meta Preview items from that one award result.

### 5th ceremony: two winner results

Fredric March and Wallace Beery are both represented as winners. The Academy treated the outcome as a tie under the rules in force at the time, so the ceremony contains two explicit winner results rather than inferring winner state from ordering.

### Stable identity over display text

Repeated winners are deduplicated by TMDB Person ID, not by name text. The generator rejects one TMDB Person ID mapping to multiple canonical names so punctuation or spelling drift cannot silently create conflicting identities.

## Artwork coverage

Final Issue #6 artwork coverage was verified against `davecollections/nuvio-people-assets` commit `ab0db998de43b9bee3c7e299a0ac8df19e8c9757`.

- 87 unique Best Actor winners
- 87 identities resolved by TMDB Person ID
- 87 identities with `actor` membership and all required artwork
- 87 identities with the optional focus pair

The current machine-readable result is recorded in `reports/issue-17-awards-people-artwork-integration.json`. The earlier `reports/issue-6-awards-people-artwork-integration.json` and `reports/issue-4-best-actor-artwork-gaps.json` files are retained as historical snapshots. Artwork availability does not change the canonical award result or block the movie catalogue.

## Annual update process

For a new ceremony:

1. Verify the Best Actor winner and credited film against the Academy's official ceremony page or Awards Database.
2. Add one explicit `best-actor` winner result to the new canonical ceremony file.
3. Reuse the winner's existing TMDB Person ID where available; resolve and manually verify any new person identity.
4. Resolve the movie's TMDB ID and retain its IMDb `tt` ID. Confirm the IDs refer to the same film.
5. Run `python scripts/build_best_actor_outputs.py` to regenerate the movie and person outputs.
6. Run `python scripts/validate_awards_data.py`, `python scripts/build_best_actor_outputs.py --check`, and the Best Picture validator.
7. Run `python scripts/check_people_artwork_integration.py --check`; deliberately update its pinned People baseline and report when a new winner is added.
8. Test the changed manifest/catalogue in Nuvio before release.

The shared acquisition, identity-matching, ambiguity, correction, and audit policy is defined in [`awards-source-strategy.md`](awards-source-strategy.md).

## Generator validation

The generator enforces:

- ceremonies 1 through 98 with filename number/year agreement;
- 99 winner results, including both 5th-ceremony winners;
- 100 unique winning-film IMDb and TMDB relationships;
- 87 unique positive TMDB Person IDs;
- one canonical name per TMDB Person ID;
- one of `work` or `works` per result;
- the two-work exception only for the 1st ceremony;
- valid Stremio movie Meta Preview output, newest ceremony first; and
- reproducible movie and person outputs in `--check` mode.
