# Academy Awards supporting acting history

Issue: #20

## Scope

This implementation records both supporting acting winner relationships from the categories' introduction at the 9th Academy Awards through the 98th ceremony in 2026. It generates:

- `catalog/movie/academy-best-supporting-actor-winning-films.json`, containing 90 films;
- `catalog/movie/academy-best-supporting-actress-winning-films.json`, containing 90 films;
- `data/generated/academy-best-supporting-actor-winners.people.json`, containing 81 unique winners; and
- `data/generated/academy-best-supporting-actress-winners.people.json`, containing 88 unique winners.

The categories are winner-only. Leading performances and nominees remain separate.

## Award authority and enrichment snapshots

The Academy Awards Database and official ceremony pages are authoritative for who won and which work received the recognition:

- https://awardsdatabase.oscars.org/
- https://www.oscars.org/oscars/ceremonies/2026

The structured import was reconciled against `DLu/oscar_data` commit `c5e9716b7e020e70205d6b95f5a5678526c1b45f`. That dataset derives from the Academy database and supplies IMDb identities; it is an enrichment and reconciliation source, not the award authority:

- https://github.com/DLu/oscar_data/commit/c5e9716b7e020e70205d6b95f5a5678526c1b45f

All 180 canonical winner names, film titles, and IMDb relationships exactly match the pinned snapshot. Existing canonical IMDb/TMDB work pairs and People-manifest identities were reused first. The production Builder/TMDB path resolved 126 previously unenriched films and accepted each only when the returned TMDB movie exposed the expected IMDb ID. Twenty-five previously absent People identities were independently resolved by exact IMDb Person ID through the same production path.

The one-shot network bootstrap used for initial identity enrichment was removed after the canonical records were written. Ceremony JSON is the durable source of truth, and both category generators rebuild offline without API credentials.

## Category lineage and ceremony coverage

The stable local category IDs are:

- `best-supporting-actor`, with source label `ACTOR IN A SUPPORTING ROLE`; and
- `best-supporting-actress`, with source label `ACTRESS IN A SUPPORTING ROLE`.

Both categories began at the 9th ceremony. Ceremonies 1 through 8 correctly contain no supporting-acting result, while ceremonies 9 through 98 contain exactly one winner result per category. The pinned history contains no tie, joint recipient, or multi-work supporting-acting winner.

The shared acting generator therefore distinguishes repository ceremony coverage from category ceremony coverage: all 98 canonical files are validated, but these two outputs require exactly 90 category ceremonies.

## Historical identity note

At the 17th ceremony, Barry Fitzgerald was nominated in both leading and supporting categories for *Going My Way* and won Supporting Actor. The canonical records preserve the two categories as separate award relationships while reusing the same verified film and person identities. This historical nomination circumstance does not create a tie or duplicate supporting result.

## Artwork coverage and handoff

Issue #20 is audited against `davecollections/nuvio-people-assets` commit `1fe63648d173760d307751a189709b22fc20e8bf`:

| Output | Unique winners | Resolved People records | Missing People records |
| --- | ---: | ---: | ---: |
| Best Supporting Actor | 81 | 81 | 0 |
| Best Supporting Actress | 88 | 88 | 0 |

All resolved records have `actor` membership, complete required artwork, and complete optional focus pairs. The report also records one display-name difference without splitting identity: Academy `Benicio Del Toro` and People `Benicio del Toro` both use TMDB Person ID `1121`.

The authoritative machine-readable evidence is `reports/issue-20-awards-people-artwork-integration.json`. Its supporting-category `missingPeople` arrays are empty after the 25 reviewed records were published by People Assets PR #82. Artwork availability never changes the canonical award result or movie catalogue.

Reproduce the complete integration check with:

```bash
python scripts/check_people_artwork_integration.py --check
```

Normal `--check` is the release gate and requires complete identity, membership, and artwork coverage against the pinned immutable People manifest.

## Annual update process

For a new ceremony:

1. Verify both supporting acting winners and their credited films against the Academy's official ceremony page or Awards Database.
2. Add one explicit winner result for each supporting category to the new canonical ceremony file.
3. Reuse existing TMDB Person and movie identities where available; resolve new identities under the shared policy.
4. Retain each film's IMDb ID and verify that its TMDB movie exposes the same ID.
5. Regenerate both supporting acting outputs.
6. Regenerate the shared People artwork report and hand off any missing TMDB Person IDs.
7. Run the full shared and category-specific validation sequence.
8. Test the changed manifest and both catalogues in Nuvio before release.

The shared acquisition, identity-matching, ambiguity, correction, and audit policy is defined in [`awards-source-strategy.md`](awards-source-strategy.md).

## Generator validation

The shared acting generator and category configurations enforce:

- all canonical ceremony files from 1 through 98 remain structurally valid;
- exactly zero supporting results in ceremonies 1 through 8;
- exactly one result per supporting category in ceremonies 9 through 98;
- 90 unique IMDb/TMDB film relationships per category;
- 81 unique Supporting Actor and 88 unique Supporting Actress TMDB Person IDs;
- one canonical display name per category/person identity;
- valid Stremio movie Meta Preview output in newest-ceremony-first order; and
- reproducible movie and person outputs in `--check` mode.
