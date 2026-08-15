# Changelog

All notable project milestones are recorded here. This project uses semantic versioning for meaningful known-good states rather than every commit.

## [Unreleased]

### Added

- Canonical Awards data model and JSON schemas for award bodies, categories, ceremony results, identity enrichment, and reusable title/person relationships.
- Complete Academy Awards Best Picture winner source data from the 1st through 98th ceremonies.
- Reproducible Best Picture catalogue generator and `--check` validation mode.
- Best Picture history documentation covering category-name changes, ceremony-year filename edge cases, source provenance, and the nominees-catalogue deferral.
- V2 Builder Suite-style GitHub Pages landing page improvements, including manifest copy support, metadata-provider guidance, guided feedback/issue links, Builder Suite placeholder link, and TMDB attribution.
- Guided GitHub Issue forms for problem reports and improvement ideas.

### Changed

- `academy-best-picture-winners` now generates from canonical ceremony data instead of the three-title proof-of-concept seed.
- Best Picture catalogue output is ordered newest ceremony first and retains the released catalogue ID.

### Planned

- Add Academy acting/directing relationships using the shared Awards data model.
- Define broader award-body source, verification, and annual update strategy before expanding beyond the Academy core.

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
