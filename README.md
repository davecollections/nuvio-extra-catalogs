# Nuvio Extra Catalogs

A small Stremio-compatible catalogue add-on intended to provide collection sources that Nuvio and its official TMDB catalogue add-on do not currently expose.

## Current catalogues

- **Academy Awards — Best Picture Winners**
- **Academy Awards — Best Actor Winning Films**

The original V0.1 three-title seed proved the integration path in Nuvio. V0.2 keeps that catalog-only architecture, expands Best Picture to the complete winner history, and adds the first person-linked acting catalogue without duplicating canonical award records.

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
```

The corresponding Stremio resources are:

```text
/catalog/movie/academy-best-picture-winners.json
/catalog/movie/academy-best-actor-winning-films.json
```

## Awards data

Canonical award facts live under `data/awards/academy-awards/`. Generated catalogue JSON is not the source of truth.

The Academy Awards Database is the authoritative award source. IMDb IDs are retained for the proven Nuvio/Stremio metadata handoff. See `docs/best-picture-history.md` for historical category and ceremony-year notes.

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

See `docs/best-actor-history.md` for source, identity-enrichment, historical edge-case, and artwork-coverage details.

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
```

## Feedback

The GitHub Pages landing page links to guided GitHub Issue forms for bug reports and improvement ideas.

## Scope

This repository remains a **companion** to Nuvio's official TMDB catalogue add-on rather than duplicating it.

Potential later additions include the remaining acting categories, directing relationships, other Academy Award categories, and additional award bodies once their source/update strategy is defined.
