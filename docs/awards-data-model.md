# Awards Data Model

Issue: #2

## Decision summary

Awards data is stored as normalized award results, separate from generated Stremio catalogue JSON.

A single normalized result must be reusable for more than one output. For example, a Best Actor result can support both:

- a movie catalogue containing the awarded/nominated film; and
- a Nuvio native `PERSON` source using the actor's TMDB Person ID.

The model therefore preserves the relationship between the award category, ceremony, work, and credited people instead of flattening everything into movie-only catalogue rows.

## Design principles

1. **Canonical data is not presentation data.** Award facts and identity mappings live under `data/`; generated Stremio catalogue responses remain under `catalog/`.
2. **One result, multiple outputs.** Do not duplicate an acting/directing result just to generate a movie catalogue and a people-based collection.
3. **TMDB IDs are identity keys when resolved.** TMDB title IDs identify works and TMDB Person IDs identify people. Canonical award records may exist before identity enrichment is complete; generators decide which unresolved records are publishable. IMDb title IDs are preserved when available because the proven Nuvio catalogue handoff works cleanly with `tt` IDs.
4. **Ceremony year is explicit.** `ceremony.year` means the year in which the award ceremony occurred. A work's `releaseYear` is separate and must not be used as the award year.
5. **Stable local IDs are independent of display names.** Award-body and category IDs use stable slugs. Display names may change without breaking generated catalogue IDs or historical data.
6. **Historical category names may vary.** A category registry may retain aliases or historical names while keeping one stable local category ID when the award lineage is genuinely the same.
7. **People are optional, not implied.** Best Picture can contain only a work. Acting/directing results include the relevant people explicitly.
8. **A work is optional at schema level.** This allows future person-only awards such as honorary/lifetime awards, while catalogue generators can deliberately skip result types they do not support.
9. **Other recipients can be preserved without inventing fake people or works.** `recipientLabel` is available for a real recipient that is neither a TMDB work nor a person record.
10. **Source provenance is retained.** Each ceremony result file identifies the authoritative source used for the award facts. ID enrichment is a separate concern from the award source itself.
11. **Generated output is disposable.** Catalog JSON should be reproducible from normalized data and metadata enrichment; generated files are not the source of truth.

## Proposed repository structure

```text
data/
└── awards/
    └── academy-awards/
        ├── award.json
        ├── categories.json
        └── results/
            ├── 2024.json
            ├── 2025.json
            └── ...

schema/
└── award-results.schema.json

catalog/
└── movie/
    ├── academy-best-picture-winners.json
    └── ...
```

This keeps yearly maintenance small: a new ceremony normally adds one results file rather than rewriting one enormous history file.

## Award body registry

`award.json` describes the award body, not individual results.

Example:

```json
{
  "schemaVersion": 1,
  "id": "academy-awards",
  "name": "Academy Awards",
  "organization": "Academy of Motion Picture Arts and Sciences",
  "externalIds": {
    "tmdbAwardId": 1
  }
}
```

External source IDs are optional convenience mappings. The stable local `id` remains authoritative inside this repository.

## Category registry

`categories.json` gives each category a stable local identity and enough semantic information to derive useful outputs.

Example:

```json
{
  "schemaVersion": 1,
  "awardBodyId": "academy-awards",
  "categories": [
    {
      "id": "best-picture",
      "name": "Best Picture",
      "mediaType": "movie",
      "recipientKind": "work",
      "externalIds": {
        "tmdbCategoryId": 1
      }
    },
    {
      "id": "best-actor",
      "name": "Best Actor",
      "mediaType": "movie",
      "recipientKind": "person",
      "creditRole": "actor"
    },
    {
      "id": "best-director",
      "name": "Best Director",
      "mediaType": "movie",
      "recipientKind": "person",
      "creditRole": "director"
    }
  ]
}
```

`creditRole` is descriptive metadata for downstream collection generation. It does not create a second person identity system.

## Ceremony result file

Each file represents one ceremony year.

```json
{
  "schemaVersion": 1,
  "awardBodyId": "academy-awards",
  "ceremony": {
    "year": 2024,
    "number": 96
  },
  "source": {
    "name": "Academy Awards official records",
    "reference": "official ceremony/database record",
    "checkedAt": "2026-08-15"
  },
  "results": []
}
```

### Ceremony year rule

For this repository, **2024 means the ceremony held in 2024**. A film such as a 2023 release that wins at the 2024 ceremony therefore has:

```json
{
  "ceremony": { "year": 2024 },
  "work": { "releaseYear": 2023 }
}
```

This avoids the ambiguous phrase "award year".

## Result shape

A result is one nomination/win relationship within a category at a ceremony.

Required:

- `categoryId`
- `status`: `winner` or `nominee`

Optional depending on category:

- `work`
- `people`
- `recipientLabel`
- `note`

At least one of `work`, a non-empty `people` array, or `recipientLabel` must exist.

### Status semantics

`status` records the outcome of the ceremony result:

- `winner` means the nomination/result won the category.
- `nominee` means a **non-winning nominee**.

A winner is not duplicated as a second `nominee` record. If a generated output means **all nominated works or people**, it must include both `winner` and `nominee` records. A winners-only output uses only `winner` records.

This keeps one canonical result per real nomination/outcome while still allowing both winners-only and all-nominees catalogues.

### Work object

```json
{
  "mediaType": "movie",
  "title": "Oppenheimer",
  "releaseYear": 2023,
  "tmdbId": 872585,
  "imdbId": "tt15398776"
}
```

Rules:

- `mediaType` and `title` are enough to preserve a work before identity enrichment is complete.
- `tmdbId` is the primary work identity once the work has been resolved.
- `imdbId` is preserved where available for Stremio/Nuvio catalogue output.
- Generators should prefer the IMDb ID when present and may fall back to `tmdb:{tmdbId}` only when necessary and supported.
- A record intended for title catalogue output must be resolved to an acceptable output ID before publication.
- Poster/backdrop URLs do not belong in the canonical award record; they are metadata/presentation enrichment.

### Person object

```json
{
  "name": "Cillian Murphy",
  "tmdbId": 2037
}
```

A person's name can be preserved before TMDB identity enrichment is complete. Once resolved, TMDB Person ID is the canonical bridge to:

- Nuvio native `PERSON` sources;
- Nuvio native `DIRECTOR` sources where applicable; and
- existing People artwork keyed by TMDB Person ID.

A person intended for native Nuvio person/director output must have a resolved TMDB Person ID before publication.

### Other recipient label

`recipientLabel` preserves a real award recipient that is not naturally represented as a TMDB work or person, without creating a fake identity.

Example:

```json
{
  "categoryId": "special-award",
  "status": "winner",
  "recipientLabel": "Example Organization"
}
```

Generators may deliberately ignore such records until an appropriate output exists.

## Examples

### Best Picture winner

```json
{
  "categoryId": "best-picture",
  "status": "winner",
  "work": {
    "mediaType": "movie",
    "title": "Oppenheimer",
    "releaseYear": 2023,
    "tmdbId": 872585,
    "imdbId": "tt15398776"
  },
  "people": []
}
```

### Best Actor winner

```json
{
  "categoryId": "best-actor",
  "status": "winner",
  "work": {
    "mediaType": "movie",
    "title": "Oppenheimer",
    "releaseYear": 2023,
    "tmdbId": 872585,
    "imdbId": "tt15398776"
  },
  "people": [
    {
      "name": "Cillian Murphy",
      "tmdbId": 2037
    }
  ]
}
```

The same record can feed a Best Actor winning-films catalogue and a people-oriented collection definition without duplicating the award result.

### Best Director winner

```json
{
  "categoryId": "best-director",
  "status": "winner",
  "work": {
    "mediaType": "movie",
    "title": "Oppenheimer",
    "releaseYear": 2023,
    "tmdbId": 872585,
    "imdbId": "tt15398776"
  },
  "people": [
    {
      "name": "Christopher Nolan",
      "tmdbId": 525
    }
  ]
}
```

A category may contain more than one person. This is required for joint directing, writing, producing, song, and other team-style credits.

## Validation rules

JSON Schema handles structural validation. Generation/CI should additionally enforce semantic rules:

- Every `categoryId` exists in the award body's category registry.
- No duplicate result exists for the same ceremony/category/status/work/person/recipient relationship.
- Unresolved canonical records are allowed, but records selected for generated title output must have a supported title identity.
- A published work using TMDB identity has a valid positive TMDB ID.
- IMDb IDs, when present, match `^tt[0-9]+$`.
- People intended for native Nuvio person/director output have positive TMDB Person IDs.
- A `winner` is stored once and is not duplicated as `nominee`; all-nominees outputs include both statuses.
- Winner state is explicit and never inferred from array order.
- At most the historically correct number of winners is accepted for a category/year; ties and joint winners must be represented explicitly rather than rejected generically.
- IDs and names are checked for obvious mismatches during enrichment.
- Generated catalogue IDs remain stable once released.

## Source vs enrichment

Award facts and TMDB/IMDb identity enrichment should be treated as separate concerns:

```text
Authoritative award result
        ↓
normalized award record
        ↓
TMDB / IMDb identity enrichment
        ↓
output-readiness validation
        ↓
generated Nuvio/Stremio catalogue JSON
```

The award source answers **who/what was nominated or won**. TMDB/IMDb are used to identify and enrich the corresponding media/person records; they do not need to be the authoritative award source.

This separation allows authoritative award facts to be recorded even when an identity match is temporarily unresolved. The unresolved record remains valid canonical data, but cannot silently enter an output that requires an ID.

## What this model deliberately does not do

- It does not model every possible award-show concept before we need it.
- It does not store posters/backdrops in award results.
- It does not create duplicate actor/director person records.
- It does not require a live backend.
- It does not make TMDB's website-only Awards pages a scraping dependency.
- It does not force person-only/honorary/other-recipient awards into movie catalogues.

## Next implementation step

Use this model for one real Academy ceremony file and build validation/generation around Best Picture first. Acting and directing categories then reuse the same record shape rather than introducing new schemas.
