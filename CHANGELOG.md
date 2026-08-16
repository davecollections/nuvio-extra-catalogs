# Changelog

All notable project milestones are recorded here. This project uses semantic versioning for meaningful known-good states rather than every commit.

## [Unreleased]

### Added

- Shared offline awards semantic validator covering ceremony ranges, provenance, category references, duplicate relationships, and cross-file identity consistency.
- Awards source, verification, identity-matching, correction, and annual-update strategy for Issue #7.
- Durable awards correction log and explicit ceremony-coverage contract for each award body.
- Read-only GitHub Actions validation for canonical data and generated-output freshness.

### Changed

- Shared repository validation now requires declared authorities, ceremony coverage, and source review dates before category-specific output checks.

### Planned

- Add Academy Best Director relationships in Issue #5 using the shared source strategy and native Nuvio `DIRECTOR` identities.
- Complete the cross-repository People artwork integration defined by Issue #6.

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
