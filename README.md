# Nuvio Extra Catalogs

A small Stremio-compatible catalogue add-on intended to provide collection sources that Nuvio and its official TMDB catalogue add-on do not currently expose.

## Current catalogues

The manifest exposes winner-film catalogues for all 24 current competitive Academy Award categories:

- Best Picture, Directing, and all four acting categories;
- Animated Feature, Animated Short, Documentary Feature, Documentary Short, International Feature, and Live Action Short;
- Casting, Cinematography, Costume Design, Film Editing, Makeup and Hairstyling, Production Design, Sound, and Visual Effects; and
- Adapted Screenplay, Original Screenplay, Original Score, and Original Song.

The original V0.1 seed proved the integration path in Nuvio. V0.2–V0.5 established the canonical Awards model and six complete picture/acting/directing histories. V1.0 completes the other 18 current Academy categories while retaining independent lineage, count, identity, and generator contracts for every category.

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
│       └── 24 Academy winner-film catalogue responses
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
academy-best-supporting-actor-winning-films
academy-best-supporting-actress-winning-films
academy-best-director-winning-films
academy-animated-feature-film-winning-films
academy-animated-short-film-winning-films
academy-casting-winning-films
academy-cinematography-winning-films
academy-costume-design-winning-films
academy-documentary-feature-film-winning-films
academy-documentary-short-film-winning-films
academy-film-editing-winning-films
academy-international-feature-film-winning-films
academy-live-action-short-film-winning-films
academy-makeup-and-hairstyling-winning-films
academy-original-score-winning-films
academy-original-song-winning-films
academy-production-design-winning-films
academy-sound-winning-films
academy-visual-effects-winning-films
academy-adapted-screenplay-winning-films
academy-original-screenplay-winning-films
```

Every declared ID maps directly to:

```text
/catalog/movie/{catalogue-id}.json
```

## Awards data

Canonical award facts live under `data/awards/academy-awards/`. Generated catalogue JSON is not the source of truth.

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

Validate all 24 manifest declarations and every Meta Preview response with:

```bash
python scripts/validate_manifest_catalogs.py
```

See `docs/remaining-academy-category-histories.md` for the per-category counts, official lineages, colour/black-and-white branches, Sound merge, no-award gaps, ties, non-film results, pinned source, and identity coverage.

All leading/supporting acting and directing people reuse the canonical `nuvio-people-assets` manifest directly by TMDB Person ID. Reproduce the complete Issue #20 integration report with:

```bash
python scripts/check_people_artwork_integration.py --check
```

The strict check requires every current award person to resolve with the correct membership and complete canonical artwork. The development-only `--allow-incomplete` flag remains available for future machine-readable gap handoffs. See `docs/people-artwork-integration.md` for the full contract and coverage.

The other 18 categories publish movie catalogues rather than native person/director sources, so People artwork is not a release gate. Their 1,819 IMDb recipient identities, 1,723 verified TMDB mappings, and informational People-manifest coverage are reproduced with:

```bash
python scripts/check_issue24_recipient_identity_coverage.py --check
```

## GitHub Pages URLs

Landing page:

```text
https://davecollections.github.io/nuvio-extra-catalogs/
```

Manifest:

```text
https://davecollections.github.io/nuvio-extra-catalogs/manifest.json
```

Catalogue response pattern:

```text
https://davecollections.github.io/nuvio-extra-catalogs/catalog/movie/{catalogue-id}.json
```

## Feedback

The GitHub Pages landing page links to guided GitHub Issue forms for bug reports and improvement ideas.

## Scope

This repository remains a **companion** to Nuvio's official TMDB catalogue add-on rather than duplicating it.

Issue #6 established the canonical People artwork bridge without adding an awards-specific artwork layer or changing this add-on's catalog-only architecture. Issues #17 and #20 extend it across leading and supporting acting. Issue #24 completes all current Academy categories. Additional award bodies should follow the same authority, identity, deterministic generation, and independently auditable category strategy.
