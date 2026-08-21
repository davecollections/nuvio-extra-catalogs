# Remaining current Academy category histories

Issue: #24

## Scope

Issue #24 completes the 18 current competitive Academy Award categories that were not part of V0.5. Together with Best Picture, the four acting categories, and Best Director, the repository now models all 24 categories awarded at the 98th Academy Awards.

The outputs are winner-film catalogues. Retired categories that are not a documented lineage of a current category, honorary awards outside the International Feature precursor period, Governors Awards, and Scientific and Technical Awards remain outside this milestone.

## Authority and enrichment snapshots

The Academy Awards Database remains the authority for the award result, credited work, credited recipient wording, category name, and historical award status:

- https://awardsdatabase.oscars.org/
- https://www.oscars.org/oscars/ceremonies/2026

The structured reconciliation input is `DLu/oscar_data` commit `c5e9716b7e020e70205d6b95f5a5678526c1b45f`. It supplies reviewable Academy-derived rows plus IMDb work and person identities; it does not override the Academy record:

- https://github.com/DLu/oscar_data/commit/c5e9716b7e020e70205d6b95f5a5678526c1b45f

Identity enrichment used the approved production TMDB proxy. A candidate was accepted only when TMDB returned the expected external IMDb ID. When normal TMDB title/name search could not discover a candidate, Wikidata IMDb-to-TMDB properties were used only to discover a possible numeric ID; the candidate still had to return the expected IMDb ID from TMDB before it entered canonical data.

The temporary acquisition and enrichment helpers were removed after their reviewed output became canonical. All committed validation and catalogue generation is offline and requires no API key.

## Per-category contracts

The ceremony column uses ceremony numbers, not film release years. “Films” is the number of unique IMDb `tt` entries published by that catalogue. “IMDb people” counts unique credited human identities preserved from the pinned source. An unresolved TMDB identity retains its IMDb Person ID and credited name and does not affect the winner-film catalogue.

| Stable category ID | Ceremony coverage | Winner results | Work links | Catalogue films | IMDb people | Unresolved TMDB people |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `adapted-screenplay` | 1–98 | 98 | 98 | 98 | 127 | 3 |
| `animated-feature-film` | 74–98 | 25 | 25 | 25 | 45 | 1 |
| `animated-short-film` | 5–98 | 94 | 94 | 94 | 92 | 5 |
| `casting` | 98 | 1 | 1 | 1 | 1 | 0 |
| `cinematography` | 1–98 | 125 | 125 | 125 | 104 | 0 |
| `costume-design` | 21–98 | 95 | 95 | 95 | 73 | 2 |
| `documentary-feature-film` | 15–98; none at 19 | 87 | 87 | 87 | 136 | 4 |
| `documentary-short-film` | 14–98; none at 15 or 30 | 84 | 84 | 84 | 107 | 14 |
| `film-editing` | 7–98 | 92 | 92 | 92 | 100 | 0 |
| `international-feature-film` | 23–98; none at 26 | 75 | 75 | 75 | 2 | 0 |
| `live-action-short-film` | 30–98 | 71 | 71 | 71 | 106 | 13 |
| `makeup-and-hairstyling` | 54–98; none at 56 | 44 | 44 | 44 | 84 | 5 |
| `original-score` | 11–98; none at 30 | 87 | 87 | 87 | 73 | 3 |
| `original-screenplay` | 13–98; none at 21 | 85 | 85 | 85 | 120 | 0 |
| `original-song` | 7–98 | 92 | 92 | 92 | 141 | 13 |
| `production-design` | 1–98 | 123 | 124 | 124 | 203 | 8 |
| `sound` | 3–98 | 138 | 136 | 118 | 195 | 13 |
| `visual-effects` | 1–98, non-annual historically | 79 | 79 | 79 | 171 | 15 |

The permanent contracts live in `scripts/build_remaining_academy_outputs.py`. They assert every first/last ceremony, no-award gap, split-category count, tie, non-film result, total relationship count, identity count, generated filename, newest-first ordering, and unique catalogue size.

## Historical lineage decisions

### Cinematography, Costume Design, and Production Design

Black-and-white and colour awards are historical branches of the corresponding current craft category. Both winning films are preserved in ceremonies where both branches were awarded. They are not published as separate modern catalogues.

Production Design also retains the 1st ceremony result that applied to both *The Dove* and *Tempest*. This produces 123 canonical winner results, 124 work links, and 124 catalogue films.

### Sound

The current Sound category has two historical branches:

- the Sound Recording → Sound Mixing → Sound lineage; and
- the Sound Effects / Sound Effects Editing → Sound Editing lineage that merged into Sound after the 92nd ceremony.

Both branches are preserved when they ran in parallel. A film that won both branches in the same ceremony remains two canonical award results with the correct credited teams, but is emitted only once in the movie catalogue. The 85th ceremony's Sound Editing tie is represented by two explicit winner results.

The 4th and 5th ceremony Sound Recording awards were made to Paramount Publix's sound department without an associated film. They remain canonical recipient-label results and intentionally emit no catalogue item. Sound therefore contains 138 winner results and 136 film links but 118 unique catalogue films.

### International Feature Film

The five honorary foreign-language film awards before the competitive category are retained as the documented precursor lineage. The 26th ceremony had no award. Country/submitter wording remains `recipientLabel`; the winning film supplies the catalogue identity.

### Shorts and documentaries

Animated Short retains the official Cartoon/Animated lineage from the 5th ceremony. Live Action Short begins with the modern canonical lineage at the 30th ceremony; retired Comedy, Novelty, Colour, One-reel, and Two-reel short categories are not silently folded into it.

Documentary Feature preserves four winners at the 15th ceremony and the 59th-ceremony tie. Documentary Short preserves its 22nd-ceremony tie. Live Action Short preserves ties at the 67th and 98th ceremonies.

### Visual Effects

The current lineage includes Engineering Effects, Special Effects, Special Visual Effects, and Visual Effects. It was not awarded annually. The explicit no-result ceremonies are protected by the generator contract instead of being inferred from gaps.

### Writing and music

Adapted Screenplay and Original Screenplay preserve their documented modern lineages and aliases. The retired Original Story category is not merged into Original Screenplay. Original Score excludes the separate retired Song Score/Adaptation Score category. Original Song remains its own continuous category from the 7th ceremony.

One source normalization is explicit: the pinned 96th-ceremony value `Screenplay - Justine Triet` is stored as the person name `Justine Triet`; the IMDb/TMDB identity and award relationship are unchanged.

## Recipient identities and People artwork

The 18 categories contain 1,819 unique IMDb-identified people. The production TMDB verification path resolves 1,723 of them; 96 retain a credited name and IMDb Person ID without an accepted TMDB match. All 1,071 unique winning-film IMDb identities have verified TMDB matches, while the catalogue contract continues to use IMDb `tt` IDs for cross-provider metadata resolution.

`reports/issue-24-academy-recipient-identity-coverage.json` records every recipient, category membership in this milestone, TMDB resolution state, and informational coverage against `nuvio-people-assets` commit `1fe63648d173760d307751a189709b22fc20e8bf`.

There is no People Assets publication handoff for Issue #24. These are movie catalogues, so Nuvio renders movie artwork. No new native `PERSON` or `DIRECTOR` output is published for the craft recipient roles, and the current People manifest models actor/director memberships. The canonical identities are preserved so a future compatible native source can add its own reviewed artwork/membership contract without re-importing award facts.

## Output and validation

Generate all 18 catalogues:

```bash
python scripts/build_remaining_academy_outputs.py
```

Validate canonical data, all category contracts, all manifest/catalogue relationships, and recipient coverage:

```bash
python scripts/validate_awards_data.py
python scripts/build_remaining_academy_outputs.py --check
python scripts/validate_manifest_catalogs.py
python scripts/check_issue24_recipient_identity_coverage.py --check
```

The resulting manifest contains 24 movie catalogues and 2,054 unique catalogue Meta Preview items. Existing V0.5 catalogue payloads remain unchanged.

## Annual update

For ceremony 99 and later:

1. Verify all 24 winner results against the Academy authority and official ceremony page.
2. Add the new ceremony file and extend `award.json` coverage.
3. Preserve the exact credited work, people/team, result branch, ties, and any absence of a film relationship.
4. Add IMDb work/person identities and accept TMDB mappings only after external-ID confirmation.
5. Update the permanent expected counts and any new historical exception deliberately.
6. Regenerate the affected catalogue and Issue #24 identity report.
7. Run the complete CI-equivalent check sequence and perform Nuvio acceptance before publication.
