# AGENTS.md

## Purpose

This repository provides additional Stremio-compatible catalog sources for Nuvio where useful collection data is not already exposed natively or through Nuvio's official TMDB catalogue add-on.

## Current phase

V1.0 is complete. Its commit-pinned preview and refreshed live manifest passed Nuvio acceptance, the deployed GitHub Pages landing page, manifest, and all 24 catalogue payloads byte-match merge commit `a49585b53bcfd95cadfb8f9a2077a02f41d82310`, and the exact tested state is preserved on `release/v1.0.0`. V1.0 completes all current Academy categories while preserving the six released V0.5 catalogue payloads unchanged. The previous V0.5 rollback point remains preserved on `release/v0.5.0`.

## Guardrails

- Do not duplicate the full official Nuvio TMDB catalogue add-on unless there is a demonstrated need.
- Reuse existing components, helpers, data mappings, schemas, artwork conventions, validators, and interaction patterns before creating new ones. If functionality is being recreated, prefer extending or reusing the existing implementation and document any justified exception.
- Prefer IMDb `tt` IDs for add-on catalogue items where cross-add-on metadata resolution is required.
- Keep catalog IDs stable once users may have installed the manifest or used a catalogue in a Collection.
- `manifest.json` catalogue IDs must exactly match their corresponding files under `catalog/{type}/`.
- Catalog responses must use valid Stremio Meta Preview objects.
- Keep this add-on catalog-only unless a future requirement proves that a `meta` resource or live backend is necessary.
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

## Post-merge housekeeping

After a pull request is merged:

- Confirm the related GitHub Issue is closed or update it with any remaining work.
- Confirm `main` contains the intended merged result before starting the next issue.
- In the local clone, switch back to `main`, fetch/pull the latest changes, and make sure the working tree is clean.
- Delete the merged local feature branch once it is no longer needed and there are no uncommitted changes on it.
- Delete the merged remote feature branch unless it is intentionally retained.
- Prune stale remote-tracking branches so deleted remote branches do not remain visible locally.
- Do not delete `main`, release branches such as `release/v0.1.0`, or branches intentionally preserved as rollback points.
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

## Next milestone

Select the next award body in a focused issue and declare its authority before import. Reuse the V1.0 canonical model, identity verification, manifest validation, compact landing-page disclosure, and independently auditable category contracts. When a second award body is ready, scope award-body-level manifest selection while preserving the current all-awards manifest URL and keeping category selection out of the user configuration.
