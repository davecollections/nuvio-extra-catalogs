# Awards corrections log

This is the durable audit trail for corrections to already-committed canonical award records. Initial imports, pre-merge review fixes, and deterministic regeneration are documented in their issue/PR and do not require a correction row.

Do not delete or rewrite an existing correction row. Add a later row that explicitly supersedes it.

| Checked date | Issue / PR | Canonical record | Before → after | Authoritative evidence | Output impact |
| --- | --- | --- | --- | --- | --- |
| — | — | No post-release canonical corrections recorded. | — | — | — |
| 2026-09-26 | #43 / #42 (preview) | BAFTA Television Specialist Factual, 1988: *A Simple Man* | IMDb-only `tt0269866` → add exact TMDB movie `494464`; retain title and 1987 year | IMDb/TMDB reciprocal ID relationship and Gillian Lynne / L. S. Lowry production context; `identity-overrides.json` | Verified TMDB poster replaces missing MetaHub image; catalogue and IMDb IDs unchanged. |
| 2026-09-26 | #43 / #42 (preview) | BAFTA Television Specialist Factual, 1997: *Rhythm: Leaving Home* | IMDb-only `tt0379127` → add reviewed TMDB series `243767`; retain original *Leaving Home* title and 1996 broadcast year | IMDb production description, Arthaus/Unitel seven-part Simon Rattle catalogue and TMDB DVD-edition description; `identity-overrides.json` | Verified poster for the same production; catalogue and IMDb IDs unchanged. TMDB's 2005 DVD date is not imported as the original broadcast year. |

The required correction workflow is defined in [`awards-source-strategy.md`](awards-source-strategy.md#corrections).
