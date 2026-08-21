# Changelog

All notable project milestones are recorded here. This project uses semantic versioning for meaningful known-good states rather than every commit.

## [Unreleased]

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

### Pending V0.5 integration

- Load the commit-pinned `0.5.0` preview in Nuvio and verify both 90-film catalogues, metadata resolution, and Folder/Collection use.

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
