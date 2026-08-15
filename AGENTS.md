# AGENTS.md

## Purpose

This repository provides additional Stremio-compatible catalog sources for Nuvio where useful collection data is not already exposed natively or through Nuvio's official TMDB catalogue add-on.

## Current phase

V0.1 is a proof of concept. Keep changes deliberately small until the Nuvio integration behaviour is proven.

## Guardrails

- Do not duplicate the full official Nuvio TMDB catalogue add-on during the proof-of-concept phase.
- Prefer IMDb `tt` IDs for catalogue items while testing cross-add-on metadata resolution.
- Keep catalog IDs stable once users may have installed the manifest.
- `manifest.json` catalogue IDs must exactly match their corresponding files under `catalog/{type}/`.
- Catalog responses must use valid Stremio Meta Preview objects.
- Do not add automated scraping of TMDB award web pages.
- Do not commit API keys, tokens, credentials, or secrets.
- Historical awards data should eventually have a documented, maintainable source and generation process.
- Treat GitHub Pages as static hosting unless a future requirement genuinely needs a live backend.

## V0.1 success criteria

- Manifest installs in Nuvio.
- Best Picture catalogue loads.
- Catalogue can participate in the intended Nuvio Collections flow.
- Clicking a seeded IMDb-ID movie resolves usable metadata through the user's other installed metadata provider.
