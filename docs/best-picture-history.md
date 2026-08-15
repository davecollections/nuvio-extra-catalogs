# Academy Awards Best Picture history

Issue: #3

## Scope

This implementation records one canonical `best-picture` winner for every Academy Awards ceremony from the 1st ceremony in 1929 through the 98th ceremony in 2026, then generates the existing `academy-best-picture-winners` Stremio catalogue from those records.

The released catalogue ID stays unchanged so existing Nuvio Collections continue to reference the same source.

## Award authority and identity enrichment

The Academy Awards Database is the authoritative source for the award result:

- https://awardsdatabase.oscars.org/

The public `DLu/oscar_data` dataset was used as an IMDb identity cross-check because it maps Academy nominations to IMDb IDs. It is an enrichment helper, not the authority for who won:

- https://github.com/DLu/oscar_data

Canonical ceremony files therefore cite the Academy Awards Database as their award source and retain IMDb IDs for the proven Nuvio/Stremio metadata handoff.

## Ceremony file naming

Ceremony files use:

```text
NNN-YYYY.json
```

where `NNN` is the zero-padded ceremony number and `YYYY` is the calendar year in which that ceremony took place.

Examples:

```text
001-1929.json
002-1930.json
003-1930.json
004-1931.json
...
098-2026.json
```

The ceremony number is required because the 2nd and 3rd Academy Awards both took place in 1930. A year-only filename would collide and would incorrectly imply that ceremony year is unique.

The 6th ceremony was held in 1934, so there is intentionally no `*-1933.json` file.

## Best Picture category lineage

The stable local category is `best-picture`. Historical Academy display names changed over time, including:

- Outstanding Picture
- Outstanding Production
- Outstanding Motion Picture
- Best Motion Picture
- Best Picture

These are aliases of the same local category lineage for this project.

At the 1st Academy Awards there was also a separate **Unique and Artistic Picture** category. This implementation follows the Academy's Best Picture lineage represented by **Outstanding Picture**, whose winner was *Wings*. It does not merge the separate Unique and Artistic Picture winner (*Sunrise*) into the Best Picture winners catalogue.

## Nominees catalogue decision

Issue #3 does not publish a Best Picture nominees catalogue yet.

The source data is rich enough to support nominees for most ceremonies, but early Academy history is not uniform. In particular, for the 2nd Academy Awards there were no official nomination announcements or nomination certificates; only winners were revealed, while other titles in Academy records were under consideration.

Publishing a single catalogue labelled “all Best Picture nominees” would therefore require an explicit historical policy for those early ceremonies. That decision is deferred rather than silently treating under-consideration titles as equivalent to later official nominees.

## Generated catalogue

Run:

```bash
python scripts/build_best_picture_catalog.py
```

The generator:

- reads the canonical ceremony result files;
- requires one Best Picture winner per ceremony;
- validates ceremony number/year against the filename;
- requires a valid IMDb `tt` ID;
- rejects duplicate ceremony numbers and duplicate IMDb IDs;
- checks that ceremony numbers form a continuous sequence;
- writes newest ceremony first;
- supplies a poster preview using Stremio's established MetaHub IMDb poster pattern.

Validation without rewriting the catalogue:

```bash
python scripts/build_best_picture_catalog.py --check
```

Poster previews use:

```text
https://images.metahub.space/poster/medium/{imdbId}/img
```

The poster URL is presentation enrichment only; it is not stored as an award fact in the canonical ceremony data.
