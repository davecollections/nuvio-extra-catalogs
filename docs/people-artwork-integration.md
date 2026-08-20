# Awards People artwork integration

Issues: #6 and #17

## Purpose

Academy Awards people reuse Nuvio's canonical People identity and artwork system. This repository does not store person artwork, copy artwork URLs into canonical award results, or introduce an awards-specific person convention.

The shared key is the numeric TMDB Person ID:

```text
canonical award result
        ↓ tmdbId
generated PERSON / DIRECTOR output
        ↓ tmdbPersonId
Builder People manifest lookup
        ↓
canonical People artwork and category membership
```

## Verified external baselines

The current deterministic integration report extends the Issue #6 contract for Issue #17 and pins the exact external states it uses:

- People artwork: [`davecollections/nuvio-people-assets`](https://github.com/davecollections/nuvio-people-assets) commit `4277be3dcfe3b6806568438ca5408d89ce29f4b2`.
- Builder migration: [`davecollections/tmdb-id-lookup`](https://github.com/davecollections/tmdb-id-lookup) merge commit `e9eb3b24a93b7e6bbca295a340d035cb018293d9` from PR #119.
- Builder baseline verified to contain that migration: `fa79389eda7d5ed59707420a16839055e7555b8c`.

The Builder loads the schema-v2 People manifest from `nuvio-people-assets`, indexes it by numeric `tmdbPersonId`, and treats the manifest as the active V2 authority for canonical name, actor/director membership, and registered artwork. The production runtime follows the manifest on `main`; this repository pins an immutable commit and manifest SHA-256 for reproducible coverage checks.

## Resolution contract

An Awards person record contains only the credited name and TMDB Person ID. The generated category output changes `tmdbId` to the explicit consumer-facing field `tmdbPersonId`; it does not add presentation data.

When the Builder finds that ID in the canonical People manifest, it uses:

| People manifest asset | Builder/Nuvio use |
| --- | --- |
| `assets.poster` | Poster-shaped person folder cover |
| `assets.landscape` | Landscape-shaped person folder cover |
| `assets.titleLogo` | Separate title logo |
| `assets.hero` | Hero/background artwork |
| `assets.focusPoster` and `assets.focusLandscape` | Optional all-or-nothing static focus pair |

Every asset is consumed from its manifest-supplied HTTPS URL. The supplied SHA-256 is the cache identity; stable paths or record counts are not cache versions.

Category membership is also resolved from the same manifest record:

- Best Actor requires `actor` membership and is intended for native `PERSON` sources.
- Best Actress requires `actor` membership and is intended for native `PERSON` sources.
- Best Director requires `director` membership and is intended for native `DIRECTOR` sources.
- A person who is both an actor and director has one TMDB identity, one asset directory, and both memberships. Kevin Costner (`1269`) is the pinned Issue #6 example; no artwork is copied for his director role.

## Fallback

If a future Awards person is not registered in the People manifest, the Builder preserves the TMDB identity and uses the TMDB profile-artwork fallback. If no profile is available, it uses the person emoji fallback.

Active V2 behavior must not reconstruct a legacy `nuvio-assets` People URL. Artwork availability never changes the canonical award result, the generated movie catalogue, or the person/director identity output.

## Current coverage

Against the pinned People commit:

| Awards output | Native source | Required membership | Resolved | Core artwork | Focus pair |
| --- | --- | --- | ---: | ---: | ---: |
| Best Actor winners | `PERSON` | `actor` | 87/87 | 87/87 | 87/87 |
| Best Actress winners | `PERSON` | `actor` | 81/81 | 81/81 | 81/81 |
| Best Director winners | `DIRECTOR` | `director` | 77/77 | 77/77 | 77/77 |
| All current unique awards people | — | — | 245/245 | 245/245 | 245/245 |

Current evidence for all three person-recipient categories is [`reports/issue-17-awards-people-artwork-integration.json`](../reports/issue-17-awards-people-artwork-integration.json). The Issue #6 integration report and the Issue #4, #5, and #17 gap reports remain historical snapshots. In particular, the Best Actress gap snapshot records the 79/81 state before Luise Rainer (`125482`) and Mikey Madison (`1640439`) were registered upstream.

## Reproducing the check

The default path fetches the immutable People manifest from GitHub's production raw-content route and verifies its exact SHA-256 before checking coverage:

```bash
python scripts/check_people_artwork_integration.py --check
```

For an offline check, a local copy is accepted only when its bytes match the same pinned manifest:

```bash
python scripts/check_people_artwork_integration.py \
  --people-manifest ../nuvio-people-assets/manifests/people.json \
  --check
```

Run without `--check` to regenerate the committed report after deliberately updating the pinned external baseline.

## Production acceptance evidence

The deterministic check proves identity, membership, asset shape, URL ownership, hashes, and coverage. The deployed production Builder was also exercised through its real TMDB and People-manifest paths.

On 2026-08-20, the deployed Builder returned HTTP 200 and its published JavaScript bundle contained the canonical `nuvio-people-assets/main/manifests/people.json` reference. The live `main` People manifest and all eight core Rami Malek/Kevin Costner sample asset URLs also returned HTTP 200 with their expected WebP/PNG content types.

After Issue #17's final People publication, all 12 manifest-supplied Luise Rainer and Mikey Madison asset URLs returned HTTP 200 from the production `main` paths. Their downloaded byte counts and SHA-256 values exactly matched the commit-pinned manifest; the responses comprised ten WebP assets and two PNG title logos.

The deployed Builder's live People flow then:

- resolved Rami Malek from TMDB Person ID `17838` and displayed the exact canonical `assets/people/17838/poster.webp` URL;
- resolved Kevin Costner from TMDB Person ID `1269`, displayed the exact canonical `assets/people/1269/poster.webp` URL, and showed his shared `Acting · Directing` membership;
- created one Rami Malek folder with the Movie Credits source; and
- created one Kevin Costner folder with the Directed Movies source.

This satisfies Issue #6's sample-collection acceptance: the production Builder resolved both award people and their canonical artwork directly from TMDB Person IDs without a second identity or artwork convention.

## Nuvio client round-trip boundary

The deployed V2 workspace does not currently expose Copy JSON, Download JSON, or Send to Nuvio. A Builder-to-Nuvio client round trip therefore cannot be completed through the current production UI and is not claimed by Issue #6.

This repository changes no live catalogue, add-on manifest, or Nuvio source contract. The established `PERSON / MOVIE` and `DIRECTOR / MOVIE` source semantics were already validated in Nuvio before the artwork-authority migration; Issue #6 verifies that the Builder now resolves the same numeric identities through `nuvio-people-assets` instead of legacy artwork paths.

When the V2 export/send control becomes available, the follow-up client smoke test is:

1. Open the [deployed Builder](https://davecollections.github.io/tmdb-id-lookup/builder/) and recreate the two-folder sample above.
2. Export or send the generated collection JSON through the normal production Builder integration.
3. Load it in Nuvio and verify the person folders render canonical poster/landscape artwork, title logo, and hero from `nuvio-people-assets`.
4. Confirm Kevin Costner uses the same canonical People record for his actor/director membership rather than a duplicated director asset convention.
5. Confirm no generated People URL uses the legacy `assets/collection_covers/people/...` paths.

The optional static-focus WebP behavior was explicitly deferred by Builder PR #119 and is not a blocker for Issue #6's poster, landscape, title-logo, hero, identity, or membership acceptance.
