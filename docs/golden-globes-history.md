# Golden Globes film and television winner histories

Issue: #27

## Scope

This milestone records Golden Globes winners from the 1st ceremony in 1944 through the 83rd ceremony in 2026. It follows all 28 categories awarded in 2026 back through defensible predecessor labels:

- 15 motion-picture categories;
- 12 television categories covering series, limited/anthology series, television movies, and stand-up specials; and
- Best Podcast, which is retained as canonical award data but cannot become a Stremio catalogue.

Unrelated discontinued honours such as New Star, World Film Favorites, Television Achievement, and Special Achievement remain visible in the committed official snapshot but are not merged into a current category. The generic 1962–1969 `Television Series` award is also not assigned to Drama or Musical/Comedy because the official label does not establish either genre lineage.

## Award authority and snapshot

[Golden Globes Winners & Nominees](https://goldenglobes.com/winners-nominees/) is the award authority. The public page uses first-party WordPress API endpoints for its filters and per-year results. `scripts/fetch_golden_globes_snapshot.py` performs a reviewed winner-only acquisition from those endpoints, removes artwork thumbnails, and refuses to write unless it receives all 83 years and exactly 2,029 winner records.

The committed snapshot is `data/sources/golden-globes/official-winners-1944-2026.json`, checked on 2026-08-21. Normal validation and catalogue generation use that file offline; the live Golden Globes site is not a runtime or CI dependency.

The current-lineage mapping selects 1,689 winner records. Each canonical result retains the official source category text and source record ID so a historical alias can be audited without losing the stable local category ID.

## Category lineages

`data/awards/golden-globes/categories.json` is the reviewed mapping from official labels to stable current categories. Notable rules include:

- early `Picture`, `Picture - Comedy`, and `Picture - Musical` labels feed the current Drama and Musical-or-Comedy motion-picture lineages;
- `Foreign Film - Foreign Language` feeds the current Non-English Language lineage;
- gendered Actor/Actress wording changes are aliases, not new categories;
- `Television Movie` feeds the current Limited Series, Anthology Series, or Motion Picture Made for Television lineage;
- the historical combined leading-performance series/television-movie labels feed the corresponding current television performance category;
- both temporary 2023 supporting-performance branches feed the current combined supporting role on television; and
- `Television Series - Comedy` feeds the current Musical-or-Comedy series lineage.

The mapping is exact-label based. A new or changed official label therefore fails closed until it is reviewed and registered.

## Work and person identities

Award status always comes from the Golden Globes snapshot. TMDB and IMDb are used only to identify the credited work and determine whether it is a movie or series.

`scripts/enrich_golden_globes_identities.py` builds the reviewed map in `data/sources/golden-globes/identity-map.json`. Strict automatic acceptance requires an unambiguous normalized title candidate and a valid IMDb external ID. Ambiguous legacy titles are recorded by exact key in `identity-overrides.json` and reverified against the selected live TMDB record before being committed.

The final map contains:

- 1,069 distinct winning works, all resolved for canonical use;
- 825 distinct credited people; and
- 331 people whose TMDB identity could be reused unambiguously from the existing Academy canonical records.

The remaining people retain their official credited names. This milestone publishes work catalogues, not native person catalogues, so unresolved person enrichment and People artwork are not publication gates and the add-on has no runtime connection to a People artwork repository.

Reviewed archive exceptions include:

- the official `Dangerous Curves (UK)` text is associated with the reviewed 1950 Mexican film *Curvas peligrosas*;
- official links for John Houseman's *The Paper Chase* win and the 1978 *Julia* wins point to later/older television adaptations, while the motion-picture categories and reviewed identities establish the 1973 and 1977 films;
- the official *Fargo* page uses a film URL even though the credited work is the television series; and
- TMDB's season-specific *Dahmer — Monster: The Jeffrey Dahmer Story* record lacks an IMDb external ID, so the reviewed continuing *Monster* anthology IMDb identity is recorded explicitly.
- Nuvio preview review exposed ambiguous-title collisions for *Birdman*, *Bill*, *The High Chaparral*, *Mister Ed*, and *Weeds*. Each now has an exact reviewed override, and the identity validator rejects missing release years or unexplained work dates that follow the associated ceremony.

These are identity-enrichment decisions, not changes to who won.

## Mixed movie and series output

The Golden Globes television archive uses a shared `tv-show` URL namespace for continuing series, limited series, and television movies. That URL is not treated as a media classification. Each work's reviewed TMDB type decides its catalogue route:

- `movie` becomes `/catalog/movie/{id}.json`;
- `series` becomes `/catalog/series/{id}.json`; and
- a current mixed category receives one catalogue for each media type actually present in its history.

`scripts/audit_golden_globes_mixed_media.py` checks series resolutions for exact-title, award-year movie candidates so television films are not silently absorbed into same-title series. The review identified and corrected legacy television films including *The Betty Ford Story*, *Citizen X*, *Conspiracy*, *James Dean*, *The Rat Pack*, *Stalin*, and *You Don't Know Jack* while retaining genuine series and miniseries such as *Angels in America*, *Carlos*, and *Shōgun*.

## Deterministic generation contracts

`scripts/build_golden_globes_canonical.py` deterministically reproduces all 83 ceremony files from the committed snapshot and identity map. `data/awards/golden-globes/output-contracts.json` independently freezes, for every current category:

- first and last ceremony represented;
- winner-result and work-link counts;
- every published movie/series catalogue ID and display name; and
- per-media work-link and unique-item counts.

`scripts/build_golden_globes_outputs.py` generates 33 catalogues containing 1,591 unique Meta Preview items: 22 movie catalogues and 11 series catalogues. Results are ordered newest ceremony first and deduplicated only within each category/media output by IMDb title ID.

Meta Preview posters use the established MetaHub IMDb route by default. Four reviewed legacy titles whose live MetaHub poster returns 404 use explicit TMDB image-CDN fallbacks stored in the output contracts. *The Governor & J.J.* is retained as the one known title with no poster in either reviewed live source; the missing artwork is documented rather than replaced with unrelated imagery.

The root `manifest.json` remains the all-awards choice. `scripts/build_manifest_presets.py` also generates Academy-only and Golden-Globes-only manifests. Because clients resolve static catalogue routes relative to the manifest directory, each preset hosts byte-identical catalogue copies beneath its own `catalog/{type}/` path and uses a distinct add-on ID.

## Reproducible offline checks

```bash
python scripts/validate_awards_data.py
python scripts/enrich_golden_globes_identities.py --check
python scripts/build_golden_globes_canonical.py --check
python scripts/build_golden_globes_outputs.py --check
python scripts/build_manifest_presets.py --check
python scripts/validate_manifest_catalogs.py
```

The mixed-media audit and snapshot/identity refresh commands require the reviewed live services and are maintenance operations, not CI steps.

## Release acceptance

Before V1.1 is released:

1. Publish an immutable commit-pinned preview and require CI to pass.
2. Install or refresh the all-awards manifest in Nuvio.
3. Verify at least one Golden Globes movie catalogue and one series catalogue.
4. Verify both the movie and series outputs of a mixed television category.
5. Verify the Academy-only and Golden-Globes-only preset manifests install independently and expose only their selected award body.
6. Confirm full title metadata resolves through the user's compatible installed metadata provider.
7. After merge, confirm GitHub Pages payloads byte-match the accepted commit before preserving a V1.1 rollback point.
