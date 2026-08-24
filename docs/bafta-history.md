# BAFTA film and television winner histories

Issue: #33

## Scope

V1.2 covers the three main BAFTA screen programmes that can produce Stremio-compatible movie or series catalogues:

- BAFTA Film Awards;
- BAFTA Television Awards; and
- BAFTA Television Craft Awards.

The 2026 official result pages expose 81 categories in total. The initial publication audit retains 75 work-associated current lineages before historical lineage review or movie/series splitting:

| Programme | Official 2026 categories | Initial work-associated scope | Deliberate exclusions |
| --- | ---: | ---: | --- |
| Film | 28 | 25 | EE Rising Star, Fellowship, Outstanding British Contribution to Cinema |
| Television | 29 | 27 | Fellowship, Special Award |
| Television Craft | 24 | 23 | Special Award |

The P&O Cruises Memorable Moment remains in the Television audit because the official result identifies an awarded television work or moment. Publication still requires an unambiguous movie or series identity.

BAFTA Games is outside scope because the add-on has no compatible game media type. Cymru and Scotland are separate regional programmes and are not silently folded into the main BAFTA lineages. Historical Children's, Britannia, Interactive, and other discontinued programmes remain separate unless a later issue defines their own scope.

## Award authority

BAFTA is the award authority:

- [BAFTA Awards Database](https://www.bafta.org/awards/search/) provides the cross-programme archive;
- [Film results](https://www.bafta.org/awards/film/) provide the current Film categories and annual results;
- [Television results](https://www.bafta.org/awards/television/) provide the current Television categories and annual results; and
- [Television Craft results](https://www.bafta.org/awards/tv-craft/) provide the current craft categories and annual results.

The Film and Television rules state that the winners list and winners press release are the definitive source for winner information. TMDB and IMDb may identify the corresponding work and person, but they do not decide award status.

## Reviewed acquisition contract

BAFTA's annual programme result pages contain the complete server-rendered nomination set for a selected award year, with winner status, the official category label, title or person heading, associated work or credited people, and a stable BAFTA nomination ID. They are the preferred historical input. Current category-history pages provide recent `Through the years` context and stable current page references, but do not by themselves expose the full archive.

During the 2026-08-22 source audit, direct non-browser requests received BAFTA's browser-check page and the public WordPress REST content endpoints rejected anonymous access. The project will not bypass those controls or depend on the live site in CI. Reviewed acquisition must therefore:

1. load the official annual result and current category-history pages in a normal browser session;
2. export a minimal winner-only source snapshot with the exact annual page URL, BAFTA nomination ID, nomination and winner counts, and check date;
3. reject pages that show a browser challenge, error state, missing year heading, duplicate nomination ID, count mismatch, or unexpected current category label;
4. retain the official spelling and credited work/person structure without identity guesses; and
5. commit the reviewed snapshot so canonical generation and validation remain fully offline.

The acquisition helper may automate extraction from already-rendered official pages, but it must not make a scheduled browser session or the live BAFTA site a runtime dependency. The archive's search-result `Load More` interaction was not used as source data because the reviewed 2026-08-22 session duplicated records after the first 20 results. The annual result pages expose the complete year without that pagination. A future annual update repeats the reviewed acquisition for the new official results and compares it with the pinned snapshot before canonical data changes.

`data/sources/bafta/current-category-pages.json` freezes the 75 reviewed current category-history pages and the six explicit exclusions found through the official 2026 result search. It is the input registry for browser acquisition, not winner data. Validate that registry independently with:

```bash
python scripts/validate_bafta_source_registry.py
```

The reviewed winner-only records are frozen by programme in `data/sources/bafta/winners-film.json`, `winners-television.json`, and `winners-television-craft.json`. Together they retain all 78 official year routes from 1949 through 2026, including zero-result years, 3,911 winners, and 3,911 globally unique BAFTA nomination IDs. Validate the pinned annual counts, records, IDs, and exact 2026 registry reconciliation with:

```bash
python scripts/validate_bafta_source_snapshots.py
```

## Category lineage gate

The 75 initial categories are not yet 75 guaranteed catalogues. Historical category names, scopes, splits, and mergers must be reviewed before stable local IDs are assigned. In particular:

- predecessor labels are mapped only when BAFTA's own history establishes the lineage;
- a current category page and a discontinued category page are not merged merely because their wording is similar;
- ties and multiple winners remain separate canonical results;
- years with no award remain explicit coverage gaps rather than inferred omissions; and
- a person-result category is publishable only when BAFTA identifies the associated winning work.

Every accepted lineage will be exact-label based and independently frozen in output contracts. An unknown future label must fail closed until reviewed.

`data/sources/bafta/category-page-evidence.json` records exact first-party page identities for all 210 historical labels. Every record is tied to an exact winner nomination ID and winner-filtered search result; all 210 resolved with no unresolved page identities.

`data/sources/bafta/lineage-decisions.json` is the fail-closed decision layer. Each evidenced historical page must be mapped to one named current included category or explicitly excluded from this current-lineage milestone. A mapping may name another BAFTA programme when a category moved between the Television and Television Craft awards; cross-programme targets are explicit rather than inferred. All 210 historical pages now have final decisions: 119 current-lineage mappings and 91 explicit exclusions. Mixed pages that cross modern branches remain preserved in the source snapshot but are excluded from current-lineage outputs rather than guessed into one branch.

Validate the evidence and completed decisions with:

```bash
python scripts/validate_bafta_category_page_evidence.py
python scripts/validate_bafta_lineage_decisions.py --complete
```

`reports/bafta-category-lineage-audit.md` is the generated review inventory for all 291 labels, their winner counts, first/last result years, page evidence, and current decision state. Keep it current with:

```bash
python scripts/build_bafta_lineage_audit.py --check
```

`data/sources/bafta/category-definitions.json` freezes the 75 accepted current categories into stable local IDs and records the source programme, canonical media scope, recipient kind, credit role, and deterministic work field. It maps the 75 current labels plus 119 accepted historical labels to 2,886 selected winner records. Five explicit source overrides cover historical Television Craft pages whose heading/detail layout differs from the current category page. Validate the registry, every accepted source label, and all selected work references with:

```bash
python scripts/validate_bafta_category_definitions.py
```

## Movie and series classification

Film results are expected to produce movie outputs. Television and Television Craft results may refer to continuing series, limited series, television movies, documentaries, specials, episodes, or individual programmes. The official programme name does not by itself decide Stremio media type.

Each reviewed work identity must be classified through TMDB and confirmed by a compatible IMDb title ID where available:

- `movie` becomes `/catalog/movie/{id}.json`;
- `series` becomes `/catalog/series/{id}.json`; and
- a historical lineage containing both types receives one catalogue per represented media type.

Episode or moment wording must resolve to the parent movie or series only when that relationship is authoritative and unambiguous. Unresolvable broadcast segments remain canonical award facts but do not receive fabricated catalogue identities.

## People and artwork

Credited recipients are preserved as identities for future Nuvio integration and auditability. V1.2 publishes work catalogues, not native person catalogues, so person artwork is not a publication gate and no runtime connection to the People artwork repository is added.

Movie and series artwork follows the established MetaHub-by-IMDb route with explicit reviewed fallbacks only when live acceptance proves they are necessary. Missing artwork is documented; it is never replaced with unrelated imagery.

## Implementation gates

Before V1.2 publication:

1. Pin and validate the winner-only BAFTA source snapshot.
2. Finish all Film, Television, and Television Craft lineage decisions and exclusions.
3. Resolve work media types and IMDb/TMDB identities with explicit ambiguity overrides.
4. Generate deterministic canonical records and per-lineage output contracts.
5. Add BAFTA movie/series catalogues, a distinct BAFTA preset manifest, and compact landing-page metadata.
6. Run the full offline validation sequence and publish an immutable preview.
7. Test representative Film, Television, Television Craft, mixed-media, preset, metadata-provider, and Refresh Add-on behaviour in Nuvio.
8. Merge only after GitHub Pages and deployed byte-match checks pass, then preserve a V1.2 rollback point.
