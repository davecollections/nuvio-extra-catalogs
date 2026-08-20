# Nuvio Extra Catalogs

A small Stremio-compatible catalogue add-on intended to provide collection sources that Nuvio and its official TMDB catalogue add-on do not currently expose.

## Current catalogues

- **Academy Awards — Best Picture Winners**
- **Academy Awards — Best Actor Winning Films**
- **Academy Awards — Best Actress Winning Films**
- **Academy Awards — Best Director Winning Films**

The original V0.1 three-title seed proved the integration path in Nuvio. V0.2 established the canonical Awards model and complete Best Picture and Best Actor histories. V0.3 reused that model for Best Director, preserving joint credited directors without duplicating canonical award records. V0.4 extends the shared acting path to the complete Best Actress history, including the 1st ceremony's three-film award and the 41st ceremony tie.

## What V0.1 proved

1. Nuvio can install a static add-on hosted on GitHub Pages.
2. Nuvio sees `Academy Awards — Best Picture Winners` as a catalogue.
3. The catalogue can be used as a source inside Nuvio Collections.
4. Items identified by IMDb IDs can open with metadata supplied by another installed metadata provider.
5. The add-on can remain catalog-only for this architecture.

A compatible metadata provider is expected to be installed alongside Extra Catalogs. Nuvio's official TMDB add-on is the recommended example used during the proof of concept.

## Structure

```text
nuvio-extra-catalogs/
├── .github/
│   └── ISSUE_TEMPLATE/
├── assets/
├── catalog/
│   └── movie/
│       ├── academy-best-actor-winning-films.json
│       ├── academy-best-actress-winning-films.json
│       ├── academy-best-director-winning-films.json
│       └── academy-best-picture-winners.json
├── data/
│   └── awards/
│       └── academy-awards/
│           ├── award.json
│           ├── categories.json
│           └── results/
├── docs/
├── examples/
├── schema/
├── scripts/
├── AGENTS.md
├── CHANGELOG.md
├── README.md
├── index.html
└── manifest.json
```

The declared catalogue IDs are:

```text
academy-best-picture-winners
academy-best-actor-winning-films
academy-best-actress-winning-films
academy-best-director-winning-films
```

The corresponding Stremio resources are:

```text
/catalog/movie/academy-best-picture-winners.json
/catalog/movie/academy-best-actor-winning-films.json
/catalog/movie/academy-best-actress-winning-films.json
/catalog/movie/academy-best-director-winning-films.json
```

## Awards data

Canonical award facts live under `data/awards/academy-awards/`. Generated catalogue JSON is not the source of truth.

The Academy Awards Database is the authoritative award source. IMDb IDs are retained for the proven Nuvio/Stremio metadata handoff, and TMDB Person IDs bridge award recipients to Nuvio's native people/director sources and existing artwork.

Run the shared offline validation before generating or publishing any awards output:

```bash
python scripts/validate_awards_data.py
```

The authority hierarchy, permitted automation, identity-matching rules, ambiguity handling, correction log, and annual-update checklist are defined in `docs/awards-source-strategy.md`. See the category history documents under `docs/` for category-specific sourcing and exceptions.

Generate the catalogue:

```bash
python scripts/build_best_picture_catalog.py
```

Validate the data and confirm the generated catalogue is current:

```bash
python scripts/build_best_picture_catalog.py --check
```

Best Actor preserves both winning-film identities and TMDB Person IDs. Generate its movie catalogue and reusable person output with:

```bash
python scripts/build_best_actor_outputs.py
```

Validate the canonical Best Actor history and both generated outputs with:

```bash
python scripts/build_best_actor_outputs.py --check
```

See `docs/best-actor-history.md` for source snapshots, identity enrichment, historical edge cases, and artwork coverage.

Best Actress reuses the shared acting-category generator while preserving its own historical exceptions. Generate its 101-film catalogue and reusable 81-person output with:

```bash
python scripts/build_best_actress_outputs.py
```

Validate the canonical Best Actress history and both generated outputs with:

```bash
python scripts/build_best_actress_outputs.py --check
```

See `docs/best-actress-history.md` for the pinned source snapshot, identity review, the 1st-ceremony multi-work award, the 41st-ceremony tie, and People artwork coverage.

Best Director preserves associated film identities, all credited winners for joint awards, and TMDB Person IDs for native `DIRECTOR` sources. Generate its movie catalogue and reusable director output with:

```bash
python scripts/build_best_director_outputs.py
```

Validate the canonical Best Director history and both generated outputs with:

```bash
python scripts/build_best_director_outputs.py --check
```

See `docs/best-director-history.md` for source snapshots, joint-winner handling, historical category names, and artwork coverage.

Best Actor, Best Actress, and Best Director people reuse the canonical `nuvio-people-assets` manifest directly by TMDB Person ID. Validate the shared integration contract with:

```bash
python scripts/check_people_artwork_integration.py --check
```

The default check uses the immutable production GitHub raw URL pinned for Issue #17 and verifies all 245 current award people, including 81/81 Best Actress winners. See `docs/people-artwork-integration.md` for the resolution contract, current coverage, historical gap-report status, and live Nuvio acceptance procedure.

## GitHub Pages URLs

Landing page:

```text
https://davecollections.github.io/nuvio-extra-catalogs/
```

Manifest:

```text
https://davecollections.github.io/nuvio-extra-catalogs/manifest.json
```

Catalogue response:

```text
https://davecollections.github.io/nuvio-extra-catalogs/catalog/movie/academy-best-picture-winners.json
https://davecollections.github.io/nuvio-extra-catalogs/catalog/movie/academy-best-actor-winning-films.json
https://davecollections.github.io/nuvio-extra-catalogs/catalog/movie/academy-best-actress-winning-films.json
https://davecollections.github.io/nuvio-extra-catalogs/catalog/movie/academy-best-director-winning-films.json
```

## Feedback

The GitHub Pages landing page links to guided GitHub Issue forms for bug reports and improvement ideas.

## Scope

This repository remains a **companion** to Nuvio's official TMDB catalogue add-on rather than duplicating it.

Issue #6 established the canonical People artwork bridge without adding an awards-specific artwork layer or changing this add-on's catalog-only architecture. Issue #17 applies it to Best Actress. Supporting acting categories, other Academy categories, and additional award bodies should follow the same source, validation, and TMDB Person identity strategy in separate focused issues.
