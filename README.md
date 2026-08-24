# Xtra

An independent Stremio-compatible catalogue add-on intended to provide collection sources that Nuvio and its official TMDB catalogue add-on do not currently expose.

## Current catalogues

The all-awards manifest exposes 84 catalogues:

- 24 winner-film catalogues for all current competitive Academy Award categories; and
- 33 Golden Globes catalogues (22 movie and 11 series) covering the 27 current category lineages that map to Stremio media types; and
- 27 BAFTA Film catalogues (25 movie and 2 series) covering all 25 reviewed current Film lineages.

The Academy catalogues include:

- Best Picture, Directing, and all four acting categories;
- Animated Feature, Animated Short, Documentary Feature, Documentary Short, International Feature, and Live Action Short;
- Casting, Cinematography, Costume Design, Film Editing, Makeup and Hairstyling, Production Design, Sound, and Visual Effects; and
- Adapted Screenplay, Original Screenplay, Original Score, and Original Song.

Golden Globes coverage follows the current 2026 film and television categories back through their defensible historical predecessors from 1944 onward. Mixed limited-series/television-movie histories are split by each winning work's actual `movie` or `series` identity. Best Podcast is retained in canonical data but has no Stremio catalogue media type.

BAFTA Film coverage follows all 25 selected current lineages across the official 1949–2026 archive. British Short Animation and Documentary contain four reviewed historical series identities, so those lineages publish separate movie and series catalogues. The verified 1989 short *Say Goodbye* remains in canonical history but has no compatible IMDb relationship and is the sole reviewed non-catalogue work.

The original V0.1 seed proved the integration path in Nuvio. V0.2–V0.5 established the canonical Awards model and six complete picture/acting/directing histories. V1.0 completed all current Academy categories, V1.1 added Golden Globes film and television, and V1.2 adds the complete BAFTA Film scope.

## What V0.1 proved

1. Nuvio can install a static add-on hosted on GitHub Pages.
2. Nuvio sees `Academy Awards — Best Picture Winners` as a catalogue.
3. The catalogue can be used as a source inside Nuvio Collections.
4. Items identified by IMDb IDs can open with metadata supplied by another installed metadata provider.
5. The add-on can remain catalog-only for this architecture.

A compatible metadata provider is expected to be installed alongside Xtra. Nuvio's official TMDB add-on is the recommended example used during the proof of concept.

## Structure

```text
nuvio-extra-catalogs/
├── .github/
│   └── ISSUE_TEMPLATE/
├── assets/
├── catalog/
│   ├── movie/
│   └── series/
├── data/
│   └── awards/
│       ├── academy-awards/
│       ├── golden-globes/
│       └── bafta-film/
├── presets/
│   ├── academy/
│   ├── golden-globes/
│   └── bafta-film/
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

Released Academy IDs retain their existing `academy-...` names. Golden Globes and BAFTA Film IDs use stable award-prefixed `...-winning-films` or `...-winning-series` conventions. Every declared ID maps directly to:

```text
/catalog/{movie|series}/{catalogue-id}.json
```

## Awards data

Canonical award facts live under `data/awards/{award-body}/`. Generated catalogue JSON and preset copies are not the source of truth.

The Academy Awards Database is the authoritative award source. IMDb title IDs are retained for the proven Nuvio/Stremio metadata handoff. Verified IMDb Person IDs preserve recipient identity when TMDB enrichment is unavailable, while TMDB Person IDs bridge compatible award recipients to Nuvio's native people/director sources and existing artwork.

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

Both supporting categories reuse the shared acting generator with coverage beginning at the 9th ceremony. Generate their 90-film catalogues and reusable 81/88-person outputs with:

```bash
python scripts/build_best_supporting_actor_outputs.py
python scripts/build_best_supporting_actress_outputs.py
```

Validate both histories and their generated outputs with:

```bash
python scripts/build_best_supporting_actor_outputs.py --check
python scripts/build_best_supporting_actress_outputs.py --check
```

See `docs/supporting-acting-history.md` for the pinned source snapshot, identity enrichment, ceremony coverage, and complete People artwork integration.

Best Director preserves associated film identities, all credited winners for joint awards, and TMDB Person IDs for native `DIRECTOR` sources. Generate its movie catalogue and reusable director output with:

```bash
python scripts/build_best_director_outputs.py
```

Validate the canonical Best Director history and both generated outputs with:

```bash
python scripts/build_best_director_outputs.py --check
```

See `docs/best-director-history.md` for source snapshots, joint-winner handling, historical category names, and artwork coverage.

The remaining 18 categories share one bulk generator while keeping a separate permanent contract for each category. Generate or validate all 18 catalogue payloads with:

```bash
python scripts/build_remaining_academy_outputs.py
python scripts/build_remaining_academy_outputs.py --check
```

Validate the all-awards manifest, both award presets, and every movie/series Meta Preview response with:

```bash
python scripts/validate_manifest_catalogs.py
```

See `docs/remaining-academy-category-histories.md` for the per-category counts, official lineages, colour/black-and-white branches, Sound merge, no-award gaps, ties, non-film results, pinned source, and identity coverage.

The Academy person/director outputs have a historical Builder integration check against the canonical `nuvio-people-assets` manifest by TMDB Person ID. The static catalogue add-on itself does not fetch that repository at runtime. Reproduce the complete Issue #20 integration report with:

```bash
python scripts/check_people_artwork_integration.py --check
```

The strict check requires every current award person to resolve with the correct membership and complete canonical artwork. The development-only `--allow-incomplete` flag remains available for future machine-readable gap handoffs. See `docs/people-artwork-integration.md` for the full contract and coverage.

The other 18 categories publish movie catalogues rather than native person/director sources, so People artwork is not a release gate. Their 1,819 IMDb recipient identities, 1,723 verified TMDB mappings, and informational People-manifest coverage are reproduced with:

```bash
python scripts/check_issue24_recipient_identity_coverage.py --check
```

Golden Globes maintenance uses a committed first-party winner snapshot, a reviewed identity map, 83 deterministic ceremony files, and per-category output contracts. Normal offline checks require no API credentials:

```bash
python scripts/enrich_golden_globes_identities.py --check
python scripts/build_golden_globes_canonical.py --check
python scripts/build_golden_globes_outputs.py --check
python scripts/build_manifest_presets.py --check
```

Networked snapshot refresh, TMDB candidate discovery, manual-override verification, and mixed-media audits are explicit reviewed maintenance operations. See `docs/golden-globes-history.md` for the source authority, category lineages, identity exceptions, and film/series classification process.

## GitHub Pages URLs

Landing page:

```text
https://davecollections.github.io/nuvio-extra-catalogs/
```

Manifest:

```text
https://davecollections.github.io/nuvio-extra-catalogs/manifest.json
```

Award-only manifest presets:

```text
https://davecollections.github.io/nuvio-extra-catalogs/presets/academy/manifest.json
https://davecollections.github.io/nuvio-extra-catalogs/presets/golden-globes/manifest.json
```

Catalogue response pattern:

```text
https://davecollections.github.io/nuvio-extra-catalogs/catalog/{movie|series}/{catalogue-id}.json
```

## Feedback

The GitHub Pages landing page links to guided GitHub Issue forms for bug reports and improvement ideas.

## Scope

This repository remains a **companion** to Nuvio's official TMDB catalogue add-on rather than duplicating it.

Issue #6 established the canonical People artwork bridge without adding an awards-specific artwork layer or changing this add-on's catalog-only architecture. Issues #17 and #20 extend it across leading and supporting acting. Issue #24 completes all current Academy categories. Issue #27 adds Golden Globes film and television histories without adding a runtime People-assets dependency. Additional award bodies should follow the same authority, identity, deterministic generation, and independently auditable category strategy.
