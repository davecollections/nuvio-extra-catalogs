# Nuvio Extra Catalogs

A small Stremio-compatible catalogue add-on intended to provide collection sources that Nuvio and its official TMDB catalogue add-on do not currently expose.

## Current catalogue

- **Academy Awards — Best Picture Winners**

The original V0.1 three-title seed proved the integration path in Nuvio. Current development expands that same stable catalogue ID to the complete Best Picture winner history while keeping the proven catalog-only architecture.

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

The released catalogue ID is:

```text
academy-best-picture-winners
```

The corresponding Stremio resource is:

```text
/catalog/movie/academy-best-picture-winners.json
```

## Best Picture data

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
```

## Feedback

The GitHub Pages landing page links to guided GitHub Issue forms for bug reports and improvement ideas.

## Scope

This repository remains a **companion** to Nuvio's official TMDB catalogue add-on rather than duplicating it.

Potential later additions include acting/directing award relationships, other Academy Award categories, and additional award bodies once their source/update strategy is defined.
