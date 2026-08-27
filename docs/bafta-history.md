# BAFTA screen-awards source audit and Film publication

Issue: #33

## Scope

The shared source audit covers the three main BAFTA screen programmes that can produce Stremio-compatible movie or series catalogues:

- BAFTA Film Awards;
- BAFTA Television Awards; and
- BAFTA Television Craft Awards.

V1.2 publishes the complete **BAFTA Film Awards** programme: all 25 work-associated current Film lineages. V1.3 adds all 27 work-associated current **BAFTA Television Awards** lineages. BAFTA Television Craft remains deferred to V1.4 so each distinct awards programme can be completed, tested, and installed independently. Its pinned source snapshot, category lineages, and existing identity evidence remain preserved; the release split does not discard or rewrite that reviewed work.

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

`data/sources/bafta/category-definitions.json` freezes the 75 audited current categories into stable local IDs and records the source programme, canonical media scope, recipient kind, credit role, and deterministic work field. It maps the 75 current labels plus 119 accepted historical labels to 2,830 work-linked winner records and 2,902 work references. Forty-nine explicit source overrides cover label-wide historical layouts, isolated BAFTA card reversals, and the reversed 2019 Television Craft cards. Forty-four explicit multi-work splits preserve slash-delimited winner portfolios. Fifty-six early Television records repeat only the credited person or team instead of identifying a work; their exact nomination IDs are preserved as explicit no-work omissions rather than fabricated titles.

Validate the registry, every accepted source label, all selected work references, and the omission contract with:

```bash
python scripts/validate_bafta_category_definitions.py
```

`data/sources/bafta/identity-map.json` is the deterministic identity inventory for the 2,830 selected results and 2,902 work links. It contains 2,087 award-year-scoped work candidates and 3,754 credited-recipient strings, retaining exact nomination IDs, programmes, category IDs, years, title/name variants, credit roles, and canonical media scope. Award-year scoping prevents unrelated television adaptations with the same title from collapsing before identity review; resolved canonical outputs later deduplicate repeated wins by IMDb identity. Generic team labels are nomination-scoped so unrelated production teams cannot collapse into one identity. Regenerate or verify the inventory offline with:

```bash
python scripts/build_bafta_identity_seed.py --write
python scripts/build_bafta_identity_seed.py --check
python scripts/enrich_bafta_identities.py --check --attempted
```

Live TMDB enrichment is an owner-reviewed maintenance step and is never run in CI or at add-on runtime. The matcher accepts only one exact-title candidate with the required media scope, a valid TMDB-to-IMDb relationship, and a plausible release/broadcast window around the BAFTA award year. Ambiguous results remain as candidate evidence for explicit review:

```bash
python scripts/enrich_bafta_identities.py --tmdb --limit 25
python scripts/enrich_bafta_identities.py --reuse-canonical
```

The initial live pass attempted every work identity in the pre-publication audit. It accepted 1,389 unambiguous live identities, then safely reused 28 reviewed Academy/Golden Globes identities that exactly matched BAFTA's plausible candidates. Subsequent deterministic source corrections may change the inventory counts, so the generated reports are the controlling current totals. `reports/bafta-identity-review.md` retains the complete cross-programme queue; `reports/bafta-film-identity-review.md` and `reports/bafta-television-identity-review.md` are the V1.2 and V1.3 publication queues. Keep them current with:

```bash
python scripts/build_bafta_identity_review.py --write
python scripts/build_bafta_identity_review.py --check
```

The completed V1.2 Film review contains 822 award-year-scoped identities. Eight hundred and twenty-one resolve to compatible IMDb title IDs: 817 movies and four series. The series are three historical British Short Animation winners and the 1968 documentary *In Need of Special Care*; their official Film lineage is preserved while output routing follows the reviewed media type. The 1989 NFTS short *Say Goodbye* is the single reviewed non-catalogue outcome because its verified TMDB record has no IMDb relationship.

The pre-release artwork audit also exposed an identity collision in the 1986 Adapted Screenplay result. The source winner *Prizzi's Honour* now resolves to TMDB movie `2075` / IMDb `tt0089841`; it no longer repeats the same identity as the separate Leading Actor winner *Kiss of the Spider Woman*.

Canonical Film generation produces 78 ceremony-year files, 1,302 winner records, and 1,321 work links. Twenty-five category lineages generate 27 catalogues because the two mixed lineages split by media type. Reproduce the canonical import and catalogue payloads with:

```bash
python scripts/build_bafta_film_canonical.py --write --check
python scripts/build_bafta_film_outputs.py
python scripts/build_bafta_film_outputs.py --check
```

The completed V1.3 Television review contains 888 award-year-scoped identities. Eight hundred and sixty-four resolve to compatible IMDb title IDs: 165 movies and 699 series. The remaining 24 verified works are explicit non-catalogue outcomes. Their reviewed movie or series type is retained in canonical data so mixed category histories remain deterministic without inventing an ID or publishing an empty catalogue.

The selected Television lineage contains 938 source winner records and 977 work links. BAFTA's annual archive repeats seven identical Flaherty/Single Documentary winner records from 1984 through 1990 under separate nomination IDs. Canonical generation keeps the source snapshot untouched but collapses those exact duplicate relationships, producing 931 results and 970 work links across 78 ceremony-year files. The 27 category lineages generate 45 useful catalogues: 18 movie and 27 series outputs.

```bash
python scripts/enrich_bafta_identities.py --check --complete --programme television
python scripts/build_bafta_television_canonical.py --write --check
python scripts/build_bafta_television_outputs.py
python scripts/build_bafta_television_outputs.py --check
```

## Movie and series classification

Film results are expected to produce movie outputs. Television and Television Craft results may refer to continuing series, limited series, television movies, documentaries, specials, episodes, or individual programmes. The official programme name does not by itself decide Stremio media type.

Each reviewed work identity must be classified through TMDB and confirmed by a compatible IMDb title ID where available:

- `movie` becomes `/catalog/movie/{id}.json`;
- `series` becomes `/catalog/series/{id}.json`; and
- a historical lineage containing both types receives one catalogue per represented media type.

Episode or moment wording must resolve to the parent movie or series only when that relationship is authoritative and unambiguous. Unresolvable broadcast segments remain canonical award facts but do not receive fabricated catalogue identities.

## People and artwork

Credited recipients are preserved as identities for future Nuvio integration and auditability. V1.2 and V1.3 publish work catalogues, not native person catalogues, so person artwork is not a publication gate and no runtime connection to the People artwork repository is added.

Movie and series artwork follows the established MetaHub-by-IMDb route with explicit reviewed fallbacks only when live acceptance proves they are necessary. Missing artwork is documented; it is never replaced with unrelated imagery.

The V1.2 live audit checks all 821 unique published IMDb titles through that production route. Seven hundred and ninety-eight return MetaHub images. *Careless Talk* and *Seven Cities of Antarctica* use verified TMDB image-CDN fallbacks. Twenty-one principally archival short-form works have no poster in either reviewed source and remain explicit `knownUnavailablePosters` outcomes. The complete evidence is committed in `reports/bafta-film-artwork-audit.json` and can be refreshed with:

```bash
python scripts/audit_bafta_film_artwork.py
python scripts/audit_bafta_film_artwork.py --offline-check
```

The first command is an intentionally networked maintenance review. The second is the deterministic CI gate that checks the committed evidence against the published title set and poster contracts without external requests.

The V1.3 Television audit applies the same production path to all 667 unique published titles. Five hundred and sixty-three resolve through MetaHub and eight use verified TMDB image-CDN fallbacks. Ninety-six mostly archival or programme-strand identities have no poster in either reviewed source and remain explicit `knownUnavailablePosters` outcomes. Evidence is committed in `reports/bafta-television-artwork-audit.json` and validated with:

```bash
python scripts/audit_bafta_television_artwork.py
python scripts/audit_bafta_television_artwork.py --offline-check
```

## Metadata compatibility

The V1.3 acceptance pass found that poster availability and detail-page metadata are separate concerns. Nuvio's recommended production provider resolves 616 of the 667 unique BAFTA Television IMDb identities. It returns an empty or unusable `meta` response for 51 reviewed IDs, including several titles that do have valid poster artwork. Cinemeta resolves 39 of those gaps; 12 are unavailable through either reviewed provider.

The catalogue IDs remain unchanged. Instead, the all-awards and relevant award-preset manifests advertise a static `meta` resource filtered to the 51 exact IMDb IDs. Each generated response contains the reviewed ID, media type, catalogue title, release year, and available contracted poster. This is a narrow compatibility fallback, not a general metadata service, and it requires no live backend.

The networked review and deterministic offline gates are:

```bash
python scripts/audit_bafta_television_metadata.py
python scripts/audit_bafta_television_metadata.py --offline-check
python scripts/build_bafta_television_metadata_fallbacks.py --check
```

The complete provider evidence is committed in `reports/bafta-television-metadata-audit.json`. A future maintenance pass may remove an ID from the fallback contract only after the recommended provider resolves a valid full meta object for that exact movie/series identity.

## Implementation gates

Before V1.2 BAFTA Film publication:

1. Pin and validate the winner-only BAFTA source snapshot.
2. Finish all Film, Television, and Television Craft lineage decisions and exclusions.
3. Resolve or explicitly classify every BAFTA Film work identity with reviewed ambiguity overrides.
4. Generate deterministic canonical Film records and per-lineage output contracts.
5. Add BAFTA Film movie catalogues, a distinct BAFTA Film preset manifest, and compact landing-page metadata.
6. Run the full offline validation sequence and publish an immutable preview.
7. Test representative Film lineages, the BAFTA Film preset, metadata-provider behaviour, and Refresh Add-on behaviour in Nuvio.
8. Merge only after GitHub Pages and deployed byte-match checks pass, then preserve a V1.2 rollback point.

Owner acceptance completed against immutable preview commit `89b830a2977b87b72751756942e557d8c234af9a`. Representative movie and mixed-series histories resolved through the installed metadata provider. The British Short Animation series split rendered *SuperTed*, *Alias the Jester*, and *Henry's Cat* with artwork; the Documentary series split correctly retained *In Need of Special Care* with its documented unavailable-poster outcome. The preview's 173 published routes returned HTTP 200 and byte-matched the accepted commit before merge.

PR #34 subsequently merged as `6a956d934e0ffcd9f56cab9835970a0ab18f5b2c`. Main CI and GitHub Pages passed, all 173 deployed files byte-matched that merge, and the owner confirmed the live release. The known-good V1.2 state is preserved by annotated tag `v1.2.0` and its corresponding GitHub Release.
