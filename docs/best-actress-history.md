# Academy Awards Best Actress history

Issue: #17

## Scope

This implementation records the Best Actress winner relationship for every Academy Awards ceremony from the 1st ceremony in 1929 through the 98th ceremony in 2026. It generates:

- `catalog/movie/academy-best-actress-winning-films.json`, containing 101 associated winning films; and
- `data/generated/academy-best-actress-winners.people.json`, containing 81 unique winners keyed by TMDB Person ID.

The category is winner-only. Nominees and the supporting acting categories are outside this implementation.

## Award authority and enrichment snapshots

The Academy Awards Database and official ceremony pages are authoritative for who won and which work received the acting recognition:

- https://awardsdatabase.oscars.org/
- https://www.oscars.org/oscars/ceremonies/2026

The structured import was cross-checked against `DLu/oscar_data` commit `c5e9716b7e020e70205d6b95f5a5678526c1b45f`. That dataset is derived from the Academy database and supplies IMDb identities; it is an enrichment and reconciliation source, not the award authority:

- https://github.com/DLu/oscar_data/commit/c5e9716b7e020e70205d6b95f5a5678526c1b45f

All 99 canonical winner results and 101 IMDb film relationships match that pinned snapshot. Existing IMDb/TMDB work pairs and People-manifest identities were reused first. Every newly resolved movie was accepted only after the production Builder/TMDB path returned the expected IMDb ID. Luise Rainer (`125482`) and Mikey Madison (`1640439`) were initially absent from the pinned People manifest, so their identities were accepted only after an exact TMDB name search also returned their award-linked films among known credits; both were subsequently added to the canonical People manifest.

The one-shot network bootstrap used for the initial identity review was removed after the canonical records were written. Canonical ceremony JSON is the durable source of truth, and both generated outputs rebuild offline without API credentials.

## Category lineage

The pinned Academy-derived snapshot uses `ACTRESS` through the 48th ceremony and `ACTRESS IN A LEADING ROLE` from the 49th ceremony onward. Both labels represent one continuous leading-performance category and are registered as aliases of the stable local `best-actress` ID. Supporting Actress remains a separate category and is not merged into this history.

## Historical edge cases

### 1st ceremony: one award, three films

The Academy records Janet Gaynor as the winner for *7th Heaven*, *Street Angel*, and *Sunrise*. The canonical result uses one person and a `works` array containing all three films. The movie catalogue deliberately emits three Meta Preview items from that one award result.

### 3rd ceremony: final award wording

Norma Shearer's nomination listed both *The Divorcee* and *Their Own Desire*, but the final award was announced for *The Divorcee*. The canonical winner relationship therefore contains only *The Divorcee* and preserves the qualification in its result note.

### 41st ceremony: tie

Katharine Hepburn for *The Lion in Winter* and Barbra Streisand for *Funny Girl* are represented as two explicit winner results. Both films appear in deterministic source order within the ceremony.

### Stable identity over display text

Repeated winners are deduplicated by TMDB Person ID, not by name text. The shared acting generator rejects one TMDB Person ID mapping to multiple canonical names, so display spelling cannot silently create a second identity.

## Artwork coverage

Final Issue #17 coverage was checked against `davecollections/nuvio-people-assets` commit `4277be3dcfe3b6806568438ca5408d89ce29f4b2`:

- 81 unique Best Actress winners;
- 81 identities resolved with `actor` membership and complete core artwork; and
- 81 identities with the optional focus pair.

The current machine-readable result is `reports/issue-17-awards-people-artwork-integration.json`, reproduced by `scripts/check_people_artwork_integration.py`. The earlier `reports/issue-17-best-actress-artwork-gaps.json` remains a historical 79/81 snapshot from before Luise Rainer and Mikey Madison were added upstream. Artwork availability never changes the canonical award fact or blocks the movie catalogue.

## Annual update process

For a new ceremony:

1. Verify the Best Actress winner and credited film against the Academy's official ceremony page or Awards Database.
2. Add one explicit `best-actress` winner result to the new canonical ceremony file.
3. Reuse the winner's existing TMDB Person ID where available; resolve and manually verify any new identity.
4. Resolve the movie's TMDB ID and retain its IMDb `tt` ID. Confirm that both IDs refer to the same film.
5. Run `python scripts/build_best_actress_outputs.py` to regenerate the movie and person outputs.
6. Run the shared validator and every category generator in `--check` mode.
7. Regenerate and review the shared People artwork integration report; update its pinned external baseline only deliberately.
8. Test the changed manifest and catalogue in Nuvio before release.

The shared acquisition, identity-matching, ambiguity, correction, and audit policy is defined in [`awards-source-strategy.md`](awards-source-strategy.md).

## Generator validation

The shared acting generator and Best Actress configuration enforce:

- ceremonies 1 through 98 with filename number/year agreement;
- 99 winner results, including both 41st-ceremony winners;
- 101 unique winning-film IMDb/TMDB relationships;
- 81 unique positive TMDB Person IDs;
- one canonical name per TMDB Person ID;
- one of `work` or `works` per result;
- the three-work exception only for the 1st ceremony;
- valid Stremio movie Meta Preview output, newest ceremony first; and
- reproducible movie and person outputs in `--check` mode.
