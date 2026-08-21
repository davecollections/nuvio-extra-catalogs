# AGENTS.md

## Purpose

This repository provides additional Stremio-compatible catalog sources for Nuvio where useful collection data is not already exposed natively or through Nuvio's official TMDB catalogue add-on.

## Current phase

V0.5 is complete and preserved on `release/v0.5.0`. V1.0 is active under Issue #24 and completes the 18 remaining current Academy categories in one independently audited milestone. Canonical data, all 18 deterministic catalogue payloads, a 24-catalogue preview manifest, and recipient identity coverage are implemented locally; publication remains gated on complete CI-equivalent validation, commit-pinned Nuvio acceptance, and owner approval. The six released V0.5 catalogue payloads remain unchanged.

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

## Validated behaviour through V0.5

- Manifest version `0.5.0` installs and validates in Nuvio; the deployed GitHub Pages payload byte-matches the accepted merge commit.
- Best Picture catalogue loads on the Nuvio home screen.
- Best Actor Winning Films loads alongside Best Picture with 100 associated films.
- Best Actress Winning Films loads with 101 associated films in newest-ceremony-first order.
- The 41st ceremony's Best Actress tie renders both films, and the 1st ceremony's single award renders all three credited films.
- Best Supporting Actor Winning Films loads with 90 associated films in newest-ceremony-first order.
- Best Supporting Actress Winning Films loads with 90 associated films in newest-ceremony-first order.
- Best Director Winning Films loads with 99 associated films in newest-ceremony-first order.
- The 1st ceremony's separate Comedy and Dramatic directing winners both render, while joint-director winning films remain single catalogue entries.
- All 400 unique people across the five acting/directing outputs resolve the canonical People manifest by TMDB Person ID with complete required and focus artwork.
- Refresh Add-on applies the deployed manifest update without requiring reinstallation.
- The catalogue appears in Nuvio's Add Catalog selector.
- The catalogue can be added to a Folder and that Folder can be used in a Collection.
- Collection output renders the catalogue items correctly.
- Seeded IMDb-ID movies resolve full metadata through the user's compatible installed metadata provider.
- Disabling the metadata provider prevents full metadata resolution while the add-on catalogue itself remains available.

## Next milestone

Complete Issue #24 acceptance and publish V1.0 with all 24 current Academy winner-film catalogues. After V1.0, select the next award body in a focused issue, declare its authority before import, and reuse the same canonical model, identity verification, manifest validation, compact landing-page disclosure, and independently auditable category contracts.
