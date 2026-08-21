# Awards source, verification, and update strategy

Issue: #7

## Purpose

This document is the required workflow for adding or correcting canonical awards data. It applies before data is turned into a Nuvio/Stremio catalogue, person output, artwork report, or other generated artifact.

The repository remains static and catalog-only. Source acquisition and optional identity lookups may use the network during reviewed maintenance work, but committed canonical data and generated outputs must validate and rebuild offline without API credentials.

## Source hierarchy

Every award body must name its own authority before its data is added. One award body's source policy must not be assumed to apply to another.

For the Academy Awards, use this hierarchy:

| Role | Source | Policy |
| --- | --- | --- |
| Award authority | [Academy Awards Database](https://awardsdatabase.oscars.org/) | Decides who or what was nominated or won, the category wording, and the credited work. The Academy describes it as the official record. |
| Yearly official review | [Academy ceremony pages](https://www.oscars.org/oscars/ceremonies) | Human-readable verification for recent ceremonies, nominees, ties, joint recipients, credited works, and category changes. |
| IMDb identity cross-check | [`DLu/oscar_data`](https://github.com/DLu/oscar_data) | Curated reconciliation input, never the authority for the award result. Pin an exact commit. Its README documents manual acquisition from the Academy database and its IMDb identifiers; its code/data is BSD-2-Clause licensed. |
| Work/person identity enrichment | [TMDB API](https://developer.themoviedb.org/docs/finding-data) | Supplies TMDB identities and confirms supported external IDs. It does not decide award status. |
| Candidate-ID discovery when TMDB text search is insufficient | [Wikidata](https://www.wikidata.org/) | May suggest a TMDB ID from a known IMDb ID. The candidate is accepted only after TMDB itself returns the expected IMDb external ID. Wikidata never decides award status or independently proves the identity pair. |
| Nuvio artwork coverage | [`davecollections/nuvio-people-assets`](https://github.com/davecollections/nuvio-people-assets) | Reuses artwork by TMDB Person ID. Artwork availability never changes the canonical award fact. |

All 24 current Academy category histories through ceremony 98 are reconciled to `DLu/oscar_data` commit `c5e9716b7e020e70205d6b95f5a5678526c1b45f`. A future import must record its own pinned commit in the relevant category history document rather than silently following that repository's moving default branch.

## Separation of responsibilities

```text
official award authority
        ↓ reviewed acquisition
canonical ceremony JSON
        ↓ reviewed identity enrichment
TMDB / IMDb relationships
        ↓ offline validation
generated catalogue and person outputs
        ↓ Nuvio acceptance test
release
```

- The award authority answers **who or what received which result**.
- IMDb and TMDB answer **which work or person that text refers to**.
- A generator answers **how validated canonical relationships become an output**.
- Nuvio testing answers **whether the output integrates correctly**.

Generated JSON under `catalog/` and `data/generated/` is never edited as the source of a correction.

## What may be automated

Reviewed maintenance scripts may automate:

- parsing a locally saved or pinned source snapshot;
- comparing a proposed import with existing canonical records;
- generating candidate TMDB/IMDb matches;
- deterministic normalization and output generation;
- schema and semantic validation;
- completeness, duplicate, identity-consistency, and artwork-gap reports.

Automation must stop and require manual review when it finds:

- more than one plausible title or person;
- a title/year, IMDb/TMDB, person/work-credit, or source disagreement;
- a tie, joint recipient, multi-work result, category split/merge, or unexpected winner count;
- a result that cannot be traced to the declared award authority.

Do not add unattended scraping of TMDB award pages. Do not make official award web pages a scheduled runtime dependency. Do not commit API keys, downloaded credentials, or a self-writing GitHub Action. A temporary local or one-shot import helper must be removed once its reviewed output is canonical.

## Provenance requirements

Every award body registry must declare one or more `authoritativeSources`. Every ceremony file must use one of those exact name/reference pairs and contain:

- `source.name` identifying the award authority;
- `source.reference` as an absolute HTTP(S) reference;
- `source.checkedAt` recording the date on which the canonical result was checked;
- explicit `winner` or `nominee` status for every stored result.

Each award body must declare `ceremonyCoverage.firstCeremonyNumber` and `lastCeremonyNumber` in `award.json`. Adding the next ceremony requires extending that range in the same change, so a missing or extra file fails shared validation.

Each new category history document must additionally record:

- the authoritative award source and category lineage;
- any pinned bulk-import or identity-cross-check snapshot;
- deliberate text normalizations and historical exceptions;
- imported result, work-link, and person-identity counts;
- output and artwork coverage where applicable.

Use a result `note` for a material historical qualification that belongs with the record. Do not use a note to conceal an unresolved identity match.

## Identity matching policy

### Works

1. Preserve the authoritative title text and release context.
2. Prefer an existing IMDb `tt` ID from a pinned reconciliation source or a previously verified canonical record.
3. Resolve the IMDb ID through TMDB's supported external-ID lookup where possible.
4. Accept a TMDB movie match only when its external IMDb ID is the expected `tt` ID.
5. If no IMDb ID exists, compare title, original/alternate title, release year, media type, and credited people manually.
6. Store the positive TMDB ID and IMDb ID only after the relationship is unambiguous.

### People

1. Reuse an existing canonical TMDB Person ID or the same ID already used by `nuvio-people-assets`.
2. Preserve a verified IMDb Person `nm` ID when the reconciliation source provides one, including when TMDB enrichment remains unresolved.
3. Prefer external-ID lookup when a verified IMDb person ID is available.
4. Otherwise compare the person's name and credits, including the award-linked work and role.
5. Treat the numeric TMDB Person ID as the preferred cross-Nuvio identity; use one canonical display name for that ID.
6. Never choose a person from name text alone when multiple candidates exist.

### Ambiguous or conflicting matches

| Situation | Required action |
| --- | --- |
| One external ID resolves to one expected media/person record | Accept after checking type and linked work/credit. |
| Multiple plausible candidates | Leave the ID unresolved, open or update an issue, and exclude the record from outputs that require the ID. |
| Authority and enrichment source disagree on award status | The award authority wins; record and review the discrepancy. |
| IMDb and TMDB IDs point to different works | Reject the match until corrected; do not publish either ID as a pair. |
| Display spelling differs but a stable ID and authority support one identity | Normalize deliberately and document the decision in the category history. |
| Historical category semantics are unclear | Do not flatten them into an existing category without a documented lineage decision. |

## Shared validation

Run:

```bash
python scripts/validate_awards_data.py
```

The shared validator checks every award body and ceremony for:

- registry and filename consistency;
- declared ceremony coverage without missing or extra files;
- recognized category IDs and explicit statuses;
- required source URL and review date;
- structurally valid work/person relationships;
- duplicate canonical relationships within a ceremony;
- consistent IMDb-to-work, TMDB-to-work, IMDb-Person-to-person, and TMDB-Person-to-name mappings;
- category recipient/media-type compatibility.

Category-specific generators remain responsible for publication rules that cannot be generic, such as expected winner counts, known ties, multi-work exceptions, required output IDs, stable ordering, Meta Preview shape, and generated-file freshness.

`.github/workflows/validate-awards-data.yml` runs the shared validator, all current generator checks, and the pinned People integration check on relevant pull requests and pushes to `main`. It has read-only repository permission and never commits generated data. Contributors must still run the checks locally before pushing.

For the current repository, the complete check sequence is:

```bash
python scripts/validate_awards_data.py
python scripts/build_best_picture_catalog.py --check
python scripts/build_best_actor_outputs.py --check
python scripts/build_best_actress_outputs.py --check
python scripts/build_best_supporting_actor_outputs.py --check
python scripts/build_best_supporting_actress_outputs.py --check
python scripts/build_best_director_outputs.py --check
python scripts/build_remaining_academy_outputs.py --check
python scripts/validate_manifest_catalogs.py
python scripts/check_people_artwork_integration.py --check
python scripts/check_issue24_recipient_identity_coverage.py --check
```

## Adding a new ceremony

1. Open or update a focused GitHub Issue describing the ceremony and affected categories.
2. Verify results against the award body's authority and official yearly page where available.
3. Add `NNN-YYYY.json`; ceremony number and ceremony year must match the filename.
4. Set the ceremony source and current `checkedAt` date.
5. Add explicit result records. Represent ties, joint recipients, and multi-work awards directly.
6. Extend `award.json`'s `lastCeremonyNumber`.
7. Reuse verified work/person identities; resolve new identities under the policy above.
8. Run the shared validator, all affected generators in write mode, then the full check sequence.
9. Review count changes and any identity/artwork gaps. Unexpected changes block publication.
10. Use a temporary isolated manifest for Nuvio acceptance when a live catalogue changes.
11. Merge through a reviewed PR, confirm deployment, perform the live smoke test, and preserve a meaningful known-good release point.

## Adding a category or award body

Before bulk expansion:

1. Create one issue for one coherent category/body outcome.
2. For a new body, identify its official authority and add its registry, category registry, coverage range, and ceremony directory.
3. For a new category, decide category lineage, recipient kind, media type, and any aliases before import.
4. Pin and document any reconciliation snapshot. Do not import from an unpinned moving source.
5. Import canonical records separately from generated output.
6. Run shared validation and manually review all exceptions and ambiguous matches.
7. Add a category-specific generator/check only when an actual output is required; reuse current Meta Preview and person-output patterns.
8. Publish only after the canonical data, generator checks, and Nuvio integration test all pass.

## Corrections

Canonical history may be corrected, but never silently:

1. Open an issue describing the affected ceremony/result, current value, proposed value, and authoritative evidence.
2. Change canonical ceremony JSON first; regenerate disposable outputs afterward.
3. Keep the correction in a focused commit/PR that names the issue.
4. Add an entry to [`awards-corrections.md`](awards-corrections.md), including output impact.
5. Update `source.checkedAt` for records actually reverified. Do not mass-update unrelated dates.
6. Rerun shared validation, every affected generator, and relevant Nuvio tests.
7. If a released catalogue identity would change, add an explicit migration plan instead of silently changing its ID.

The correction log is append-only in meaning: if a prior correction needs amendment, add a new row that supersedes it rather than deleting the audit trail.

## Current expansion gate

All 24 current Academy categories are reference implementations. Issue #20 demonstrates native actor/director output and strict People artwork integration; Issue #24 demonstrates a single large milestone whose 18 categories still retain independent counts, lineages, no-award gaps, identity review, and deterministic output contracts. New person-recipient outputs must pass the same identity, membership, artwork, and fallback review before publication. Additional award bodies may be grouped when they share one source model and validation path, but every included category must remain independently auditable.
