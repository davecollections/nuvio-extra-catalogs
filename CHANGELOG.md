# Changelog

All notable project milestones are recorded here. This project uses semantic versioning for meaningful known-good states rather than every commit.

## [Unreleased]

No changes yet.

## [1.1.0] - 2026-08-22

### Added

- Complete Golden Globes winner histories under Issue #27 for the 28 categories awarded in 2026 and their defensible historical lineages across all 83 ceremonies from 1944 through 2026.
- A committed 2,029-record first-party Golden Globes winner snapshot, 1,689 scoped canonical results, 1,069 reviewed work identities, and 825 retained person identities.
- Thirty-three deterministic Golden Globes catalogues: 22 movie and 11 series payloads covering all 27 catalogue-compatible current categories. Best Podcast remains canonical data only because Stremio has no podcast catalogue type.
- Explicit mixed-media classification and audit tooling for series, limited series, anthology series, television movies, and stand-up specials.
- Academy-only and Golden-Globes-only static manifest presets, each with independent add-on identity and byte-matched local catalogue routes.

### Changed

- The user-facing add-on, manifest presets, landing page, documentation, and support forms now use the independent `Xtra` identity instead of `Nuvio Extra Catalogs`; stable add-on IDs, catalogue IDs, repository paths, and manifest URLs are unchanged so existing installations can refresh in place.
- The existing all-awards manifest URL advances to version `1.1.0`, declares both `movie` and `series`, and preserves all 24 released Academy catalogue IDs while adding the 33 Golden Globes IDs.
- Nuvio acceptance review corrected five ambiguous title identities: *Birdman*, *Bill*, *The High Chaparral*, *Mister Ed*, and *Weeds*. The erroneous one-item `Female Actor, Television Musical or Comedy — Films` output was removed after *Weeds* returned to its correct series route.
- Four verified TMDB poster fallbacks cover correct legacy titles whose canonical MetaHub poster URL returns 404. *The Governor & J.J.* remains explicitly recorded as having no poster in either reviewed live source.
- Shared canonical validation now accepts series and podcast relationships, preserves official source category/record identifiers, permits reviewed title aliases for an otherwise identical IMDb/TMDB work, and still rejects conflicting external identities.
- The landing page adds an all-awards/Academy/Golden Globes manifest selector and a second compact award disclosure without expanding the page by default.
- CI now reproduces the Golden Globes identity, canonical import, output, preset, and repository-wide manifest checks offline.

### Validated locally for V1.1 preview

- Shared validation passes with 2 award bodies, 52 categories, 181 ceremonies, 3,759 canonical results, 3,761 work links, and 4,088 person links.
- Golden Globes contracts pass with 1,689 results and 1,591 unique catalogue Meta Preview items across 22 movie and 11 series catalogues.
- All 1,069 distinct Golden Globes winning works have reviewed media type, TMDB ID, and IMDb ID, apart from the intentionally unsupported podcast identity.
- The all-awards manifest and both award presets pass exact route, payload-shape, media-type, byte-equality, and catalogue-set validation: 46 movie and 11 series catalogues with 3,645 total all-awards Meta Preview items.
- Desktop and 393-pixel mobile browser checks pass for manifest selection, both compact award disclosures, horizontal overflow, accessibility labelling, and console errors.

### Validated in Nuvio

- The owner accepted representative Golden Globes film and series catalogues, both sides of a mixed film/series category, all three manifest choices, the five corrected identities, and the four artwork fallbacks from immutable previews.
- Refresh Add-on changed the existing deployed installation from `Nuvio Extra Catalogs` to the working `Xtra` identity without requiring reinstallation, while retaining the Academy Awards and Golden Globes catalogues.
- Main CI and GitHub Pages passed for merge commit `bbb606999cdbff8a7d97d1fb61db2ced8c3f43c5`, and all 118 deployed landing-page, manifest, and catalogue files match that commit.

### Known-good rollback point

The exact live-tested V1.1 state is preserved on branch `release/v1.1.0` and annotated tag `v1.1.0`, both pointing to merge commit `bbb606999cdbff8a7d97d1fb61db2ced8c3f43c5`. The corresponding GitHub release records the accepted installation URLs and behaviour.

## [1.0.0] - 2026-08-21

### Added

- Complete winner histories for all 18 remaining current Academy categories under Issue #24, bringing the canonical registry and manifest to all 24 categories awarded at the 98th Academy Awards.
- Eighteen deterministic winner-film catalogue payloads containing 1,476 unique Meta Preview items, with permanent per-category contracts for ceremony coverage, result/work/person counts, ties, split categories, non-award gaps, non-film results, and catalogue deduplication.
- Historical lineage coverage for black-and-white/colour Cinematography, Costume Design, and Production Design; both merged Sound branches; the International Feature honorary precursor period; Animated Short aliases; and the non-annual Visual Effects lineage.
- Optional IMDb Person IDs in the canonical person shape, allowing reviewed recipient identity to remain machine-readable when TMDB enrichment is unavailable.
- Machine-readable Issue #24 coverage for all 1,819 IMDb-identified recipients: 1,723 verified TMDB mappings and 96 explicit unresolved identities.
- Repository-wide manifest/catalogue validation for exact filename/ID alignment and Stremio Meta Preview shape across all 24 catalogues.
- Consolidated history and annual-update documentation in `docs/remaining-academy-category-histories.md`.

### Changed

- Manifest version advances to `1.0.0` and declares all 24 current competitive Academy winner-film catalogues.
- The compact Academy Awards landing-page disclosure reports 24 catalogues and bounds the expanded list within a scrollable detail area.
- Shared identity validation now enforces consistent IMDb Person and TMDB Person mappings across categories.
- The source strategy records the pinned all-category Oscar reconciliation snapshot and permits Wikidata only for candidate-ID discovery followed by mandatory TMDB external-ID confirmation.
- Existing V0.5 catalogue payloads remain byte-identical.

### Validated locally for V1.0

- Shared validation passes with 24 categories, 98 ceremonies, 2,070 canonical results, 2,072 work links, and 2,900 person links.
- The 18 new category contracts pass with 1,495 winner results, 1,494 film links, and 1,476 unique catalogue films.
- All 1,071 unique new winning-film IMDb identities have confirmed TMDB mappings; no title identity relies on a name-only guess.
- Manifest/catalogue validation passes with 24 declared files and 2,054 total unique Meta Preview items.
- All six released V0.5 generators and the strict 400-person People artwork integration check continue to pass unchanged.
- Issue #24 publishes movie catalogues only, so its 1,661 informational missing People-assets records are not a release gate and no cross-repository artwork handoff is required.

### Validated in Nuvio

- The owner loaded immutable preview commit `a2994d7d6162adf107365bd2afe015ac7d9ebefb` and verified all 24 catalogues, including the one-film Casting history introduced at the 98th ceremony.
- Refreshing the deployed production manifest applied live version `1.0.0`, and the owner confirmed the live release.
- The deployed GitHub Pages landing page, manifest, and all 24 catalogue payloads return HTTP 200 and byte-match merge commit `a49585b53bcfd95cadfb8f9a2077a02f41d82310`.

### Known-good rollback point

The exact live-tested V1.0 state is preserved on branch `release/v1.0.0`, pointing to merge commit `a49585b53bcfd95cadfb8f9a2077a02f41d82310`.

## [0.5.0] - 2026-08-21

### Added

- Complete Academy Awards Best Supporting Actor and Best Supporting Actress winner histories from the 9th through 98th ceremonies: 90 winner results and films per category, with 81 and 88 unique TMDB Person identities respectively.
- Stable `academy-best-supporting-actor-winning-films` and `academy-best-supporting-actress-winning-films` catalogues plus reusable native `PERSON` outputs.
- Machine-readable Issue #20 People artwork coverage and handoff evidence across all five current person/director categories.

### Changed

- The shared acting generator now supports a configurable first ceremony while preserving the released leading-category outputs.
- Manifest version advances to `0.5.0`, declares both supporting-acting catalogue IDs, and exposes six Academy Awards catalogues on the landing page.
- The People integration checker adds an explicit development-only incomplete-report mode; normal CI/release checks continue to require complete coverage.

### Validated locally for V0.5

- All 180 supporting-acting winner names, film titles, and IMDb IDs exactly match the pinned Oscar snapshot.
- The production Builder/TMDB path verified 126 previously unenriched supporting-film identities against their exact IMDb IDs.
- Shared validation passes with 6 categories, 98 ceremonies, 575 results, 578 work links, and 480 person links.
- All 400 unique people across the five acting/directing outputs resolve against `nuvio-people-assets` commit `1fe63648d173760d307751a189709b22fc20e8bf` with required membership, complete core artwork, and complete focus artwork.

### Validated in Nuvio

- The owner loaded the commit-pinned `0.5.0` preview and verified all six catalogues.
- Both supporting-acting catalogues rendered 90 associated films, resolved metadata, and worked as Nuvio Folder/Collection sources.
- Refresh Add-on applied the deployed live `0.5.0` manifest, and the owner confirmed the live supporting catalogues continued to work.
- The deployed GitHub Pages landing page, manifest, and all six catalogue payloads returned HTTP 200 and byte-match merge commit `03fd3da79eda999154cefca7809cc7cef5421619`.

### Known-good rollback point

The exact live-tested V0.5 state is preserved on branch `release/v0.5.0`, pointing to merge commit `03fd3da79eda999154cefca7809cc7cef5421619`.

## [0.4.0] - 2026-08-20

### Added

- Deterministic Issue #6 integration validation against an immutable `nuvio-people-assets` manifest, including exact manifest hashing, identity and membership checks, required and optional artwork coverage, sample Actor/Director resolutions, and fallback documentation.
- Machine-readable cross-repository coverage evidence for all 164 unique Academy Best Actor and Best Director winners.
- Complete Academy Awards Best Actress winner history from the 1st through 98th ceremonies: 99 winner results, 101 associated films, and 81 unique TMDB Person identities.
- `academy-best-actress-winning-films` catalogue and reusable native `PERSON` output, with deterministic checks for Janet Gaynor's three-film 1st-ceremony award and the 41st-ceremony tie.
- Shared configurable acting-category generator reused by Best Actor and Best Actress without changing the released Best Actor outputs.
- Reproducible Issue #17 People artwork gap snapshot and final shared integration evidence against pinned canonical manifests.

### Changed

- Best Actor artwork coverage advances from 84/87 to 87/87 and Best Director advances from 62/77 to 77/77 against the pinned canonical People manifest.
- Best Actress artwork coverage advances from 79/81 to 81/81 after Luise Rainer and Mikey Madison were added to the canonical People manifest.
- Awards documentation now records the merged Builder's manifest-based People resolution and treats the older category gap reports as historical snapshots.
- Manifest version advances to `0.4.0`, declares the stable Best Actress catalogue ID, and exposes the fourth Academy Awards catalogue on the landing page.
- Shared awards validation now covers four categories and CI checks the Best Actress generated outputs and artwork report.

### Validated through the production integration

- The deployed Builder references the canonical People manifest and resolves the live Rami Malek Actor and Kevin Costner dual-role samples to their exact `nuvio-people-assets` poster URLs.
- The live People manifest and all eight core sample asset URLs returned HTTP 200 with the expected content types.
- All 12 newly published Luise Rainer and Mikey Madison asset URLs returned HTTP 200 and matched the byte counts and SHA-256 values in the pinned People manifest.
- The deployed Builder created the two-folder Actor Movie Credits / Director Directed Movies sample with no legacy People artwork convention.

### Validated locally for V0.4

- Local shared and category-specific validation passes with 395 canonical results, 398 work links, and 300 person links; Best Actress output checks pass at 101 films and 81 unique winners.
- All 83 newly introduced Best Actress film identities were confirmed through the production Builder/TMDB path against their exact IMDb IDs.
- The commit-pinned People integration check resolves all 245 unique Best Actor, Best Actress, and Best Director identities with complete required artwork; all 81 Best Actress winners also have the optional focus pair.

### Validated in Nuvio

- The owner loaded the commit-pinned `0.4.0` preview manifest in Nuvio and verified all four catalogues.
- Best Actress Winning Films rendered 101 associated films, including the 41st-ceremony tie and the 1st-ceremony three-film tail.
- Best Actress items resolved metadata and worked as a Nuvio Folder/Collection source.
- The deployed GitHub Pages manifest, landing page, and all four catalogue payloads passed live HTTP checks; the manifest and catalogue bytes match merge commit `e01244f61104735852bf0b00c603c3381760e0a5`.

### Known-good rollback point

The exact live-tested V0.4 state is preserved on branch `release/v0.4.0`, pointing to merge commit `e01244f61104735852bf0b00c603c3381760e0a5`.

### Deferred

- A current-client static-focus WebP and Builder-to-Nuvio round trip remains deferred because the deployed V2 workspace does not yet expose Copy, Download, or Send.

## [0.3.0] - 2026-08-16

### Added

- Shared offline awards semantic validator covering ceremony ranges, provenance, category references, duplicate relationships, and cross-file identity consistency.
- Awards source, verification, identity-matching, correction, and annual-update strategy for Issue #7.
- Durable awards correction log and explicit ceremony-coverage contract for each award body.
- Read-only GitHub Actions validation for canonical data and generated-output freshness.
- Complete Academy Awards Best Director winner data from the 1st through 98th ceremonies, preserving 102 director links, 77 unique TMDB Person identities, and 99 winning-film relationships.
- Deterministic Best Director movie-catalogue and native `DIRECTOR` output generator with validation for the 1st ceremony's split categories and all joint credited winners.
- `academy-best-director-winning-films` catalogue, reusable Best Director winner output, source-history documentation, and pinned artwork-gap report.

### Changed

- Shared repository validation now requires declared authorities, ceremony coverage, and source review dates before category-specific output checks.
- Manifest version advances to `0.3.0` and declares the Best Director winning-films catalogue.

### Validated in Nuvio

- The commit-pinned `0.3.0` preview manifest loads with all three Academy Awards catalogues.
- The deployed GitHub Pages manifest refreshed the existing live add-on from `0.2.0` to `0.3.0` without reinstallation and exposes all three catalogues.
- Best Director Winning Films renders 99 associated films in newest-ceremony-first order.
- The 1st ceremony's two historical directing winners and the three joint-director film cases render without duplicate film entries.
- Best Director items resolve full metadata and work as a Nuvio Folder/Collection source.

### Known-good rollback point

The exact live-tested V0.3 state is preserved on branch `release/v0.3.0`, pointing to merge commit `a5bb59cbcb8d9500a9be279db000df5837a32967`.

## [0.2.0] - 2026-08-16

### Added

- Canonical Awards data model and JSON schemas for award bodies, categories, ceremony results, identity enrichment, and reusable title/person relationships.
- Complete Academy Awards Best Picture winner source data from the 1st through 98th ceremonies.
- Reproducible Best Picture catalogue generator and `--check` validation mode.
- Best Picture history documentation covering category-name changes, ceremony-year filename edge cases, source provenance, and the nominees-catalogue deferral.
- Complete Academy Awards Best Actor winner data from the 1st through 98th ceremonies, preserving 87 TMDB Person identities and 100 winning-film relationships.
- Deterministic Best Actor movie-catalogue and person-output generator with validation for ties, the 1st ceremony's multi-film award, identity consistency, and complete ID coverage.
- `academy-best-actor-winning-films` catalogue and reusable Best Actor winner person output.
- Best Actor history documentation covering authoritative sourcing, pinned enrichment snapshots, historical edge cases, and People artwork coverage.
- V2 Builder Suite-style GitHub Pages landing page improvements, including manifest copy support, metadata-provider guidance, guided feedback/issue links, Builder Suite placeholder link, and TMDB attribution.
- Guided GitHub Issue forms for problem reports and improvement ideas.

### Changed

- `academy-best-picture-winners` now generates from canonical ceremony data instead of the three-title proof-of-concept seed.
- Best Picture catalogue output is ordered newest ceremony first and retains the released catalogue ID.
- Manifest version advances to `0.2.0` and declares the new Best Actor winning-films catalogue.

### Validated in Nuvio

- Both production catalogues render from the deployed GitHub Pages manifest.
- Best Actor preview and live-manifest refresh tests passed with approximately 100 results and the known multi-work/tie edge cases.
- Refresh Add-on applied manifest version `0.2.0` without reinstalling the add-on.

### Known-good rollback point

The exact tested V0.2 state is preserved on branch `release/v0.2.0`, pointing to commit `50ab94008b1a4691e9a13a13a35fd9fe39dc5488`.

## [0.1.0] - 2026-08-15

### Added

- Initial static Stremio-compatible `manifest.json` hosted through GitHub Pages.
- `Academy Awards — Best Picture Winners` proof-of-concept movie catalogue.
- Three seeded IMDb-ID movies: Oppenheimer, Everything Everywhere All at Once, and Parasite.
- Static catalogue endpoint under `catalog/movie/academy-best-picture-winners.json`.

### Validated in Nuvio

- Manifest installs and validates successfully.
- Catalogue renders on the Nuvio home screen.
- Catalogue appears in Nuvio's Add Catalog selector.
- Catalogue can be used as a Folder source inside a Nuvio Collection.
- Collection output renders catalogue items correctly.
- IMDb-ID items hand off successfully to a compatible installed metadata provider for full movie metadata.
- The add-on can remain catalog-only for this architecture.

### Known-good rollback point

The exact tested V0.1 state is preserved on branch `release/v0.1.0`, pointing to commit `45e571a537c3fc89d3f4fee2b37b59b387ca4b8d`.
