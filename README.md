# Nuvio Extra Catalogs

A small Stremio-compatible catalogue add-on intended to provide collection sources that Nuvio and its official TMDB catalogue add-on do not currently expose.

## V0.1 proof of concept

The first test exposes one movie catalogue:

- **Academy Awards — Best Picture Winners**

It currently contains only a small seed set. The purpose of V0.1 is to prove the integration path before building the full awards dataset.

## What V0.1 proved

1. Nuvio can install a static add-on hosted on GitHub Pages.
2. Nuvio sees `Academy Awards — Best Picture Winners` as a catalogue.
3. The catalogue can be used as a source inside Nuvio Collections.
4. Items identified by IMDb IDs can open with metadata supplied by another installed metadata provider.
5. The add-on can remain catalog-only for this architecture.

A compatible metadata provider is therefore expected to be installed alongside Extra Catalogs. Nuvio's official TMDB add-on is the recommended example used during the proof of concept.

## Structure

```text
nuvio-extra-catalogs/
├── .github/
│   └── ISSUE_TEMPLATE/
├── .nojekyll
├── AGENTS.md
├── CHANGELOG.md
├── README.md
├── assets/
├── index.html
├── manifest.json
└── catalog/
    └── movie/
        └── academy-best-picture-winners.json
```

The catalogue ID declared in `manifest.json` is:

```text
academy-best-picture-winners
```

Under the Stremio add-on protocol, the corresponding resource is therefore:

```text
/catalog/movie/academy-best-picture-winners.json
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

The GitHub Pages landing page links to guided GitHub Issue forms for bug reports and improvement ideas. Use those forms where possible so reproduction details and user value are captured consistently.

## Scope

For now, this repository should remain a **companion** to Nuvio's official TMDB catalogue add-on rather than duplicating it.

Potential later additions include other Academy Award categories and additional award bodies once the data-source approach has been settled.

## Data note

V0.1 is manually seeded for technical testing. It is not intended to be a complete historical Best Picture dataset yet.
