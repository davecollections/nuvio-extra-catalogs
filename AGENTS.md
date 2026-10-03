# AGENTS.md

## Purpose

This repository provides additional Stremio-compatible catalog sources for Nuvio where useful collection data is not already exposed natively or through Nuvio's official TMDB catalogue add-on.

## Current phase

V1.4 BAFTA Television Craft is released. PR #42 merged as `d9219c73d87064947e6e9c8fb380dfe62c1bdbd4`, preserved by annotated tag `v1.4.0` and its GitHub Release. Main CI and GitHub Pages passed, and all 512 deployed public files byte-matched the merge on 2026-09-26. The owner accepted its unchanged public payload from preview `2f00ae2dc3c5cbe3581278905842c7f957e71a35` based on prior Nuvio browsing and the poster audit, choosing to stop further visual checks. The manifest remains `1.4.0` with 172 catalogues and 6,323 items. Issue #43 retains 145 pending production-credit diagnostics and unresolved identities; release approval does not clear them. Planning Issue #44 and PR #49 are complete. Issue #45 implements official Emmy source acquisition and historical lineage review, followed by #46–#48; `docs/emmy-history.md` records the source inventory and implementation gates. `Xtra` remains a working identity: do not rename the repository, GitHub Pages path, or other stable routes until the owner explicitly approves the final brand.

## Guardrails

- Do not duplicate the full official Nuvio TMDB catalogue add-on unless there is a demonstrated need.
- Reuse existing components, helpers, data mappings, schemas, artwork conventions, validators, and interaction patterns before creating new ones. If functionality is being recreated, prefer extending or reusing the existing implementation and document any justified exception.
- Prefer IMDb `tt` IDs for add-on catalogue items where cross-add-on metadata resolution is required.
- Keep catalog IDs stable once users may have installed the manifest or used a catalogue in a Collection.
- Keep the released add-on IDs and manifest URLs stable during user-facing brand changes so existing installations can refresh in place.
- `manifest.json` catalogue IDs must exactly match their corresponding files under `catalog/{type}/`.
- Static preset manifests must carry distinct add-on IDs and host byte-matched catalogue and relevant metadata routes beneath their own manifest directory; do not assume a client resolves preset resources from the repository root.
- Catalog responses must use valid Stremio Meta Preview objects.
- Keep this add-on catalogue-led. The V1.3 acceptance evidence justifies exact static `meta` fallbacks for reviewed provider gaps; do not broaden them into a general metadata resource or add a live backend without a separate demonstrated requirement.
- The add-on may rely on another compatible installed metadata provider, such as Nuvio's official TMDB add-on, for full title metadata.
- Do not add automated scraping of TMDB award web pages.
- Do not commit API keys, tokens, credentials, or secrets.
- Historical awards data must follow `docs/awards-source-strategy.md`, including a documented authority, reviewed identity enrichment, shared validation, and a maintainable generation process before expansion.
- Preserve TMDB Person IDs in awards data when a category relates to a person so the data can integrate with Nuvio native `PERSON` / `DIRECTOR` sources and existing People artwork.
- Preserve verified IMDb Person IDs when TMDB person enrichment is unavailable; never substitute a name-only guess for an unresolved external identity.
- Treat GitHub Pages as static hosting unless a future requirement genuinely needs a live backend.

## Reuse-first rule

Before creating a new file format, helper, mapping, validator, artwork lookup, source type, or interaction pattern, check whether an equivalent already exists in this repository or in the established Nuvio/TMDB collection workflow. Reuse or extend first. Create a parallel implementation only when the existing one cannot meet the requirement cleanly.

## Development workflow

- Track meaningful work in GitHub Issues before implementation where practical.
- Keep each issue focused on one coherent outcome.
- Make small, understandable commits tied to the active issue.
- Run `python scripts/validate_awards_data.py` before category-specific generators and checks whenever canonical awards data changes.
- Test catalogue/manifest changes in Nuvio before considering the issue complete.
- Use semantic versions for meaningful known-good milestones rather than every commit.
- Preserve known-good release points so rollback is straightforward.
- Do not change a released catalogue ID without an explicit migration plan.

## Release preservation

- Preserve every owner-accepted milestone with an annotated semantic-version tag and a corresponding GitHub Release.
- Verify the tag resolves to the exact accepted commit before deleting any branch that previously preserved that release.
- Permanent `release/*` branches are not required for rollback. Create a temporary maintenance branch from the annotated tag only when an older version genuinely needs a patch, and delete it after the maintenance work is merged or otherwise preserved.
- GitHub's automatically generated source archives are sufficient unless a release needs an additional purpose-built asset.
- Never move or reuse a published release tag. Corrections require a new semantic version.

## Post-merge housekeeping

After a pull request is merged:

- Confirm the related GitHub Issue is closed or update it with any remaining work.
- Confirm `main` contains the intended merged result before starting the next issue.
- In the local clone, switch back to `main`, fetch/pull the latest changes, and make sure the working tree is clean.
- Delete the merged local feature branch once it is no longer needed and there are no uncommitted changes on it.
- Delete the merged remote feature branch unless it is intentionally retained.
- Prune stale remote-tracking branches so deleted remote branches do not remain visible locally.
- Do not delete `main`, published release tags, or branches that still contain unmerged work. Redundant release or maintenance branches may be deleted only after their accepted commit is protected by a verified annotated tag and GitHub Release.
- If the merged work changes the live manifest/catalogue, confirm GitHub Pages has deployed successfully and perform the relevant Nuvio smoke test.
- Update `CHANGELOG.md` when the merge completes a notable milestone or changes released behaviour.
- Create or preserve an appropriate version/tag/release point when the merged work represents a meaningful known-good release.

## Validated behaviour through V1.0

- Manifest version `1.0.0` installs and validates in Nuvio with all 24 current Academy winner-film catalogues.
- The owner accepted the immutable 24-catalogue preview, refreshed the deployed live add-on, and confirmed the live release.
- The deployed landing page, manifest, and all 24 catalogue payloads return HTTP 200 and byte-match the accepted merge commit.
- Shared validation covers 24 categories, 98 ceremonies, 2,070 canonical results, 2,072 work links, and 2,900 person links.
- The 18 V1.0 category contracts cover 1,495 winner results and 1,476 unique catalogue films, including historical split branches, ties, explicit no-award gaps, and non-film Sound results.
- Casting correctly begins at the 98th ceremony with one winning film.
- Best Picture catalogue loads on the Nuvio home screen.
- Best Actor Winning Films loads alongside Best Picture with 100 associated films.
- Best Actress Winning Films loads with 101 associated films in newest-ceremony-first order.
- The 41st ceremony's Best Actress tie renders both films, and the 1st ceremony's single award renders all three credited films.
- Best Supporting Actor Winning Films loads with 90 associated films in newest-ceremony-first order.
- Best Supporting Actress Winning Films loads with 90 associated films in newest-ceremony-first order.
- Best Director Winning Films loads with 99 associated films in newest-ceremony-first order.
- The 1st ceremony's separate Comedy and Dramatic directing winners both render, while joint-director winning films remain single catalogue entries.
- All 400 unique people across the five acting/directing outputs resolve the canonical People manifest by TMDB Person ID with complete required and focus artwork.
- The 18 V1.0 categories preserve 1,819 IMDb-identified recipients, including 1,723 verified TMDB mappings and 96 explicit unresolved identities; their movie-only outputs require no People artwork handoff.
- Refresh Add-on applies the deployed manifest update without requiring reinstallation.
- The catalogue appears in Nuvio's Add Catalog selector.
- The catalogue can be added to a Folder and that Folder can be used in a Collection.
- Collection output renders the catalogue items correctly.
- Seeded IMDb-ID movies resolve full metadata through the user's compatible installed metadata provider.
- Disabling the metadata provider prevents full metadata resolution while the add-on catalogue itself remains available.

## Validated behaviour through V1.1

- Manifest version `1.1.0` installs and validates with 57 catalogues: 46 movie and 11 series outputs containing 3,645 all-awards Meta Preview items.
- Golden Globes coverage spans all 83 ceremonies from 1944 through 2026, retaining 1,689 current-lineage results, 1,069 reviewed work identities, and 825 people across 33 catalogue outputs.
- Representative Golden Globes movie, series, and mixed film/series histories resolve correctly through the installed metadata provider.
- The all-awards, Academy-only, and Golden-Globes-only manifest choices install with distinct stable add-on IDs and the intended catalogue sets.
- Acceptance review corrected *Birdman*, *Bill*, *The High Chaparral*, *Mister Ed*, and *Weeds* and verified four TMDB poster fallbacks. *The Governor & J.J.* is the sole documented work without artwork in either reviewed source.
- The deployed landing page uses the independent working `Xtra` identity and explicitly states that the project is not affiliated with or endorsed by Nuvio.
- Refresh Add-on changed the existing installation to `Xtra` without requiring reinstallation and retained both award bodies.
- Main CI and GitHub Pages passed, and all 118 deployed files byte-match accepted merge commit `bbb606999cdbff8a7d97d1fb61db2ced8c3f43c5`.
- The known-good release is preserved by annotated tag `v1.1.0` and its corresponding GitHub Release at accepted merge commit `bbb606999cdbff8a7d97d1fb61db2ced8c3f43c5`.

## Validated behaviour through V1.2

- Manifest version `1.2.0` installs and validates with 84 catalogues: 71 movie and 13 series outputs containing 4,963 all-awards Meta Preview items.
- BAFTA Film coverage spans all 25 reviewed current lineages across the official 1949–2026 archive, retaining 1,302 canonical winner records and 1,321 work links across 27 catalogue outputs.
- The BAFTA Film preset installs independently, while the all-awards manifest retains Academy Awards and Golden Globes alongside BAFTA Film.
- Owner acceptance covered representative movie and mixed-series histories through the installed metadata provider, including *SuperTed*, *Alias the Jester*, *Henry's Cat*, and the documented unavailable-poster outcome for *In Need of Special Care*.
- Main CI and GitHub Pages passed, and all 173 deployed files byte-match accepted merge commit `6a956d934e0ffcd9f56cab9835970a0ab18f5b2c`.
- The known-good release is preserved by annotated tag `v1.2.0` and its corresponding GitHub Release.

## Validated behaviour through V1.3

- Manifest version `1.3.0` installs and validates with 129 catalogues: 89 movie and 40 series outputs containing 5,751 all-awards Meta Preview items.
- BAFTA Television covers all 27 reviewed current lineages across 78 annual archives, retaining 931 canonical winner records and 970 work links across 45 catalogue outputs.
- Seven exact duplicate Single Documentary relationships in the reviewed source snapshot are collapsed deterministically during canonical generation without altering the source evidence.
- All 888 scoped Television identity units are reviewed: 864 resolve to 165 movie and 699 series relationships, while 24 are explicit non-catalogue outcomes.
- The BAFTA Television preset validates independently, while the all-awards manifest retains Academy Awards, Golden Globes, and BAFTA Film.
- Live artwork review covers all 667 unique published titles: 563 use MetaHub, eight use verified TMDB fallbacks, and 96 are explicit unavailable-poster outcomes.
- Live metadata review covers all 667 unique published titles: 616 resolve through Nuvio's recommended provider and 51 have exact static fallback routes; Cinemeta resolves 39 of those provider gaps and 12 are unavailable through either reviewed provider.
- Static metadata fallbacks preserve the existing IMDb catalogue IDs and are advertised only as exact full-ID prefixes. Normal full metadata remains the responsibility of compatible installed providers.
- Owner acceptance against corrected immutable preview commit `e8da9ad671648fe3915255aaa98a51681268b38a` confirmed compact movie fallbacks for *Friday Night Live* and both Stanley Baxter titles, the compact series fallback for *Timmy and Vicki*, and unaffected full provider metadata for *Robbie the Reindeer: Hooves of Fire*.
- Main CI and GitHub Pages passed, and all 367 deployed landing-page, manifest, preset, catalogue, and metadata files byte-match accepted merge commit `860a79cff358393137b4a28ad25d60b5a1faf2a1`.
- The known-good release is preserved by annotated tag `v1.3.0` and its corresponding GitHub Release.

## Next milestone

Issue #45 source implementation is in progress on `work/issue-45-emmy-sources` through draft PR #50. The official snapshot reconciles all 78 indices and 5,437 links, inventories 500 historical page slugs, and captures 2,587 candidate winner records across 2,480 pages plus one independently reconciled no-award page. The 49 selected 2026 winners are cross-checked against official releases. The ledger excludes 350 fields, accepts 112 lineage decisions and retains 38 branches with unresolved historical periods. Accepted page/year/winner allocations cover 2,275 pages and 2,324 records, with 67 pinned first-party context sources. Retained scope exclusions include 14 pages and 15 marked winners: nine pages from five whole-field exclusions plus five year-specific variety/personality exclusions within partly pending performance branches. The audit must count both kinds; excluding a field or period must not erase its inspected facts. Columbo's 1975 and Upstairs, Downstairs's 1976 supporting performances follow the original winning year's Limited Series eligibility rather than another season's Drama classification. Early music, mystery/western and quiz programme branches have explicit format decisions; both sides of the 1954 This Is Your Life/What's My Line? tie are retained under their reviewed hosted/game formats. The 1978 Lou Grant/Rockford and 1977 Waltons single appearances follow ongoing-drama Guest histories, preserving original Lead headings. Grease: Live and the 65th Annual Tony Awards (2012) use pinned live-broadcast production evidence; other Special Class formats remain pending. The original Astaire (1959), Liza (1973), Stritch (2004), Bennett (2007) and Mr. Warmth (2008) programme awards follow Prerecorded Variety with actual recorded-production evidence, retaining the Variety award for the two documentary films. Live singing is not a live telecast; restoration dates and producer profiles do not rewrite ceremony years or missing credits. The French Chef (1966) and David Brinkley's Journal (1962) follow Hosted Nonfiction from first-party host-format accounts; their original NET/NBC broadcasters and role/n/a credit evidence survive. KFI-TV University remains pending. Berg's 1951 Goldbergs and Ball's 1953 I Love Lucy performances follow Comedy lead actress, preserving original N/A credits. The Civil War (1991), Nature (1989) and The Twentieth Century (1960/1961 Public Service) follow Documentary/Nonfiction Series using first-party production histories. Both 1988 Nature/Buster Keaton winners are now reviewed in Documentary/Nonfiction Series, retaining the original Academy Series heading and every credit. PBS's specific American Masters production records establish the Keaton film and the Gish/Murrow documentary specials (1989/1991 awards), without replacing Academy ceremony years or recipient evidence. The 1995 Baseball/TV Nation tie remains wholly pending until both winners are reviewed. Scared Straight! (1979) and Lucy and Desi: A Home Movie (1993) follow Documentary/Nonfiction Special using first-party interview captions; The Barbara Walters Specials (1983) follows the original recurring interview programme in Hosted Nonfiction, separately from the later Ten Most Fascinating People specials. Other early comedian fields, the tied 1975 supporting performances and How the West Was Won remain under review. Pinned Foundation interview/context evidence is permitted separately from the main Academy award-fact authority; validate both requested and redirected hosts. Reviewed broadcaster production context is permitted only beneath the PBS American Masters archive and never replaces Academy award facts, no-award evidence or original credits. Sixteen source pages remain unresolved (15 without explicit winner markers and one first-party conflict), alongside 120 winner-credit diagnostics. Greg Garrison's profile repeats the disputed 1969 database result and does not independently resolve the conflict with the Academy's history. These are source-review counts, not accepted canonical identities or complete histories. `validate_emmy_source.py --complete` must fail until review is finished; default validation blocks Emmy catalogue publication while those gates remain open. No canonical Emmy identities or public outputs exist yet.

The owner approved the expanded-essentials Emmy plan in `docs/emmy-history.md`: 49 current categories across comedy, drama, limited/anthology and TV movies, animation, documentary/nonfiction, reality, variety, game shows and narration. Use one Television Academy award family and preset covering Primetime and Creative Arts together, following selected lineages through the 1949–2026 archive. Retain the complete 121-category inventory with explicit included/deferred/excluded dispositions. Defer short-form and specialist craft; exclude commercials, emerging media, honorary awards and separate Emmy competitions. Counts describe selected current categories, not verified historical winner or catalogue totals. Begin with source and lineage issue #45, then identities/canonical data #46, outputs and live audits #47, and acceptance/release #48. Use canonical body `emmy-awards`, prefix `emmy-`, preset `emmys` and add-on ID `com.davecollections.nuvio.extra.emmys`. Preserve presentation night as evidence rather than a permanent catalogue boundary. Keep Issue #43 open; Dingo and People artwork remain deferred. No Emmy catalogue is published by the planning work.

### Owner direction recorded 2026-09-16

- The Dingo branding preview is deferred and preserved on `work/dingo-brand-preview` at `9fc0592`. Retain that branch for possible future review; do not open a PR or merge it without new owner direction. Continue released work under Xtra.
- Issue #41 tracks BAFTA Television Craft. Finish BAFTA before starting Emmy implementation.
- Owner artwork preference (2026-09-26): retain blank posters when verified real artwork is unavailable. Do not generate placeholder/title cards. Use verified real programme artwork; withhold generic title-only graphics even when supplied by a third party.
- Audit actor/director identities against the current published `nuvio-people-assets` manifest and maintain `reports/awards-actor-director-artwork.md` as the assets handoff. Keep verified missing artwork, membership changes, optional focus artwork, and unresolved person identities separate. The owner will coordinate artwork generation with the assets task.
- For Emmys, use the Television Academy as the award-fact authority and reviewed IMDb/TMDB identities for enrichment. The owner supplied `https://www.themoviedb.org/award/83-creative-arts-emmy-awards` as a useful reference. Preserve the prohibition on automated TMDB award-page scraping. Review Primetime and Creative Arts coverage together, with distinct other Emmy programmes requiring explicit scope decisions.

### V1.4 accepted checkpoint — 2026-09-26

- The owner asked to continue Craft without People artwork work. Keep the existing pinned handoff as background evidence; do not expand artwork scope.
- Craft generation covers 23 lineages, 589 canonical results and 619 work links. All 497 scoped work identities are reviewed: 486 resolve and 11 are explicit non-catalogue outcomes. Forty-three catalogues contain 576 items across 434 unique titles.
- V1.4 has 172 catalogues and a separate Craft preset. Craft catalogue IDs use `bafta-craft-` so they do not overlap the released Television preset's `bafta-television-` prefix. All 129 previous catalogue IDs remain stable, including the now-empty Sports Coverage Films route.
- Live Craft audits find 381 MetaHub posters, 11 TMDB fallbacks, 42 unavailable posters, 402 provider-resolved titles and 32 compact fallback IDs. The shared Festival of Remembrance identity is corrected to IMDb `tt10069230` in Television and Craft.
- Television retains 931 results and 970 work links across 45 catalogues. Its 888 scoped identity decisions comprise 861 compatible relationships and 27 explicit non-catalogue outcomes after production corrections. Its 663 published titles use 559 MetaHub posters, 13 TMDB fallbacks and two TVDB fallbacks; 89 have no verified available poster through checked routes. Metadata resolves 612 titles through Nuvio, with 51 exact static fallbacks. Shared generation publishes 77 unique fallback routes across Television and Craft.
- All 43 workflow checks and 17 regression tests passed for the accepted preview; all 512 immutable public files byte-matched it. The owner accepted the known gaps and expressly ended further visual checking. Do not claim a fresh exhaustive Nuvio test. Publication subsequently completed: main CI and Pages passed, all 512 live files byte-matched merge `d9219c73d87064947e6e9c8fb380dfe62c1bdbd4`, and its annotated tag/GitHub Release `v1.4.0` is preserved. Issue #41 is closed and the merged Craft branch was removed; the deferred Dingo branch remains.
- Issue #43 retains 145 pending production-credit diagnostics, the Trouble in Tahiti ambiguity, and withheld productions needing compatible IMDb identities. Do not bulk-mark these verified or turn genuine gaps into invented artwork.
