#!/usr/bin/env python3
"""Build and enrich the reviewed Golden Globes identity map.

The committed official snapshot decides award status. TMDB is used only to attach
stable work/person identities. Network enrichment is a reviewed maintenance step;
offline generation consumes the resulting committed identity map.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = (
    REPO_ROOT
    / "data"
    / "sources"
    / "golden-globes"
    / "official-winners-1944-2026.json"
)
CATEGORIES_PATH = REPO_ROOT / "data" / "awards" / "golden-globes" / "categories.json"
IDENTITY_MAP_PATH = (
    REPO_ROOT / "data" / "sources" / "golden-globes" / "identity-map.json"
)
OVERRIDES_PATH = (
    REPO_ROOT / "data" / "sources" / "golden-globes" / "identity-overrides.json"
)
ACADEMY_RESULTS_DIR = REPO_ROOT / "data" / "awards" / "academy-awards" / "results"
TMDB_API_ROOT = "https://api.themoviedb.org/3"
TOKEN_ENV = "TMDB_API_READ_TOKEN"
TRAILING_ARTICLE_RE = re.compile(r"^(?P<title>.+),\s*(?P<article>The|A|An)$", re.IGNORECASE)
DISAMBIGUATION_RE = re.compile(r"\s*\((?:TV|\d{4}(?:\s+TV\s+Series)?)\)\s*$", re.IGNORECASE)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


class IdentityError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise IdentityError(f"{path}: expected a JSON object")
    return value


def snapshot_digest(snapshot: dict) -> str:
    """Hash snapshot content independently of checkout line-ending policy."""
    canonical = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def source_labels(categories: dict) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for category in categories.get("categories", []):
        if not isinstance(category, dict):
            raise IdentityError(f"{CATEGORIES_PATH}: invalid category entry")
        labels = [category.get("name"), *category.get("aliases", [])]
        for label in labels:
            if not isinstance(label, str) or not label.strip():
                raise IdentityError(f"{CATEGORIES_PATH}: invalid source label")
            previous = mapping.get(label)
            if previous is not None and previous.get("id") != category.get("id"):
                raise IdentityError(f"source label {label!r} maps to multiple categories")
            mapping[label] = category
    return mapping


def clean_text(value: str) -> str:
    current = value
    for _ in range(3):
        decoded = html.unescape(current)
        if decoded == current:
            break
        current = decoded
    return " ".join(current.replace("–", "-").replace("—", "-").split()).strip()


def title_variants(value: str) -> list[str]:
    value = clean_text(value)
    variants = [value]
    without_suffix = DISAMBIGUATION_RE.sub("", value).strip()
    if without_suffix and without_suffix not in variants:
        variants.append(without_suffix)
    match = TRAILING_ARTICLE_RE.fullmatch(without_suffix)
    if match:
        reordered = f"{match.group('article')} {match.group('title')}"
        if reordered not in variants:
            variants.append(reordered)
    return variants


def normalized_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", clean_text(value)).encode("ascii", "ignore").decode()
    return NON_ALNUM_RE.sub("", value.casefold())


def entity_key(item: dict, *, kind: str, year: int, category_media_type: str) -> str:
    link = item.get("link")
    if isinstance(link, str) and link.strip():
        parsed = urlparse(link)
        path = f"{parsed.path.rstrip('/')}/"
        # The official archive reuses a small number of film posts for remakes
        # with identical titles (for example, Les Misérables in 1996 and 2013).
        # Film identities are therefore award-cycle scoped; television posts
        # remain stable across a programme's multi-year run.
        if kind == "work" and category_media_type == "movie" and "/film/" in path:
            return f"{path}#{year}"
        return path
    return f"official:{item.get('officialId')}"


def select_work_item(category: dict, winner: dict) -> dict | None:
    show = winner.get("show")
    if isinstance(show, dict):
        return show
    recipients = winner.get("recipients", [])
    if category.get("recipientKind") == "work" and recipients:
        return recipients[0]
    if category.get("mediaType") == "podcast" and recipients:
        return recipients[0]
    return None


def add_entity(
    registry: dict[str, dict],
    item: dict,
    *,
    year: int,
    category_id: str,
    category_media_type: str,
    kind: str,
) -> None:
    key = entity_key(
        item, kind=kind, year=year, category_media_type=category_media_type
    )
    title = clean_text(item["title"])
    entry = registry.setdefault(
        key,
        {
            "key": key,
            "kind": kind,
            "officialLink": item.get("link"),
            "officialIds": [],
            "officialTypes": [],
            "titles": [],
            "ceremonyYears": [],
            "categoryIds": [],
            "categoryMediaTypes": [],
        },
    )
    for field, value in (
        ("officialIds", item.get("officialId")),
        ("officialTypes", item.get("type")),
        ("titles", title),
        ("ceremonyYears", year),
        ("categoryIds", category_id),
        ("categoryMediaTypes", category_media_type),
    ):
        if value is not None and value not in entry[field]:
            entry[field].append(value)


def academy_people_by_name() -> dict[str, dict]:
    candidates: dict[str, set[tuple[int | None, str | None]]] = {}
    names: dict[str, str] = {}
    for path in sorted(ACADEMY_RESULTS_DIR.glob("*.json")):
        payload = load_json(path)
        for result in payload.get("results", []):
            for person in result.get("people", []):
                name = person.get("name")
                if not isinstance(name, str) or not name.strip():
                    continue
                normalized = normalized_title(name)
                names.setdefault(normalized, name.strip())
                candidates.setdefault(normalized, set()).add(
                    (person.get("tmdbId"), person.get("imdbId"))
                )
    resolved: dict[str, dict] = {}
    for normalized, values in candidates.items():
        identified = {value for value in values if value[0] is not None or value[1] is not None}
        if len(identified) == 1:
            tmdb_id, imdb_id = next(iter(identified))
            resolved[normalized] = {
                "name": names[normalized],
                **({"tmdbId": tmdb_id} if tmdb_id is not None else {}),
                **({"imdbId": imdb_id} if imdb_id is not None else {}),
                "method": "academy-canonical-reuse",
            }
    return resolved


def build_seed(snapshot: dict, categories: dict, existing: dict | None) -> dict:
    labels = source_labels(categories)
    works: dict[str, dict] = {}
    people: dict[str, dict] = {}
    matched_results = 0
    for year_entry in snapshot.get("years", []):
        year = year_entry.get("year")
        for group in year_entry.get("groups", []):
            category = labels.get(group.get("officialCategory"))
            if category is None:
                continue
            for winner in group.get("winners", []):
                matched_results += 1
                work_item = select_work_item(category, winner)
                if work_item is not None:
                    add_entity(
                        works,
                        work_item,
                        year=year,
                        category_id=category["id"],
                        category_media_type=category["mediaType"],
                        kind="work",
                    )
                if winner.get("nomineeType") == "people":
                    for person in winner.get("recipients", []):
                        add_entity(
                            people,
                            person,
                            year=year,
                            category_id=category["id"],
                            category_media_type=category["mediaType"],
                            kind="person",
                        )

    previous_works = {
        entry.get("key"): entry for entry in (existing or {}).get("works", [])
    }
    previous_works_by_link: dict[str, list[dict]] = {}
    for entry in (existing or {}).get("works", []):
        link = entry.get("officialLink")
        if isinstance(link, str) and link:
            previous_works_by_link.setdefault(link, []).append(entry)
    previous_people = {
        entry.get("key"): entry for entry in (existing or {}).get("people", [])
    }
    academy_people = academy_people_by_name()

    for key, entry in works.items():
        prior = previous_works.get(key, {})
        if not prior and len(previous_works_by_link.get(entry.get("officialLink"), [])) == 1:
            candidate_prior = previous_works_by_link[entry["officialLink"]][0]
            if len(candidate_prior.get("ceremonyYears", [])) == 1:
                prior = candidate_prior
        for field in ("resolution", "candidates", "reviewNote"):
            if field in prior:
                entry[field] = prior[field]
        for field in (
            "officialIds",
            "officialTypes",
            "titles",
            "ceremonyYears",
            "categoryIds",
            "categoryMediaTypes",
        ):
            entry[field].sort()
        if entry["categoryIds"] == ["podcast"]:
            entry["resolution"] = {
                "mediaType": "podcast",
                "title": entry["titles"][0],
                "method": "official-unsupported-media",
            }
            entry.pop("candidates", None)
    for key, entry in people.items():
        prior = previous_people.get(key, {})
        for field in ("resolution", "candidates", "reviewNote"):
            if field in prior:
                entry[field] = prior[field]
        if "resolution" not in entry:
            matches = {
                normalized_title(title): academy_people.get(normalized_title(title))
                for title in entry["titles"]
            }
            reusable = {json.dumps(value, sort_keys=True): value for value in matches.values() if value}
            if len(reusable) == 1:
                entry["resolution"] = next(iter(reusable.values()))
        for field in (
            "officialIds",
            "officialTypes",
            "titles",
            "ceremonyYears",
            "categoryIds",
            "categoryMediaTypes",
        ):
            entry[field].sort()

    snapshot_hash = snapshot_digest(snapshot)
    return {
        "schemaVersion": 1,
        "awardBodyId": "golden-globes",
        "snapshotSha256": snapshot_hash,
        "matchedCurrentCategoryWinnerRecords": matched_results,
        "works": sorted(works.values(), key=lambda entry: entry["key"]),
        "people": sorted(people.values(), key=lambda entry: entry["key"]),
    }


def tmdb_json(path: str, token: str, params: dict | None = None) -> dict:
    url = f"{TMDB_API_ROOT}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "nuvio-extra-catalogs-reviewed-maintenance/1.0",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            value = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise IdentityError(f"TMDB request failed for {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IdentityError(f"TMDB returned an invalid response for {path}")
    return value


def candidate_titles(candidate: dict) -> list[str]:
    values: list[str] = []
    for key in ("title", "original_title", "name", "original_name"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip() and value not in values:
            values.append(value.strip())
    return values


def candidate_year(candidate: dict) -> int | None:
    for key in ("release_date", "first_air_date"):
        value = candidate.get(key)
        if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])
    return None


def rank_candidate(entry: dict, candidate: dict) -> tuple:
    official_normalized = {
        normalized_title(variant)
        for title in entry["titles"]
        for variant in title_variants(title)
    }
    candidate_normalized = {normalized_title(title) for title in candidate_titles(candidate)}
    exact = bool(official_normalized & candidate_normalized)
    media_type = candidate.get("media_type")
    link = entry.get("officialLink") or ""
    expected_media_types = set(entry.get("categoryMediaTypes", []))
    expected_tmdb_type = (
        "movie"
        if expected_media_types == {"movie"}
        else "tv"
        if expected_media_types == {"series"}
        else None
    )
    source_preference = 2 if (
        (expected_tmdb_type is not None and media_type == expected_tmdb_type)
        or (
            expected_tmdb_type is None
            and (
                ("/film/" in link and media_type == "movie")
                or ("/tv-show/" in link and media_type == "tv")
            )
        )
    ) else 1
    year = candidate_year(candidate)
    expected_years = [value - 1 for value in entry["ceremonyYears"]]
    year_distance = min((abs(year - value) for value in expected_years), default=999) if year else 999
    popularity = candidate.get("popularity") or 0
    return (1 if exact else 0, source_preference, -year_distance, popularity)


def summarize_candidate(candidate: dict) -> dict:
    return {
        "mediaType": "series" if candidate.get("media_type") == "tv" else "movie",
        "tmdbId": candidate.get("id"),
        "title": (candidate.get("name") or candidate.get("title")),
        "originalTitle": (candidate.get("original_name") or candidate.get("original_title")),
        "releaseYear": candidate_year(candidate),
        "popularity": candidate.get("popularity"),
    }


def enrich_work(entry: dict, token: str) -> tuple[str, dict | None, list[dict]]:
    if entry.get("resolution", {}).get("imdbId"):
        return entry["key"], entry["resolution"], entry.get("candidates", [])
    candidates_by_id: dict[tuple[str, int], dict] = {}
    for title in entry["titles"]:
        for query in title_variants(title):
            payload = tmdb_json(
                "/search/multi",
                token,
                {"query": query, "include_adult": "false", "language": "en-US", "page": 1},
            )
            for candidate in payload.get("results", []):
                if candidate.get("media_type") not in {"movie", "tv"}:
                    continue
                candidate_id = candidate.get("id")
                if isinstance(candidate_id, int):
                    candidates_by_id[(candidate["media_type"], candidate_id)] = candidate
            if candidates_by_id:
                break
        if candidates_by_id:
            break
    ranked = sorted(
        candidates_by_id.values(), key=lambda value: rank_candidate(entry, value), reverse=True
    )
    summaries = [summarize_candidate(value) for value in ranked[:8]]
    if not ranked:
        return entry["key"], None, summaries

    top = ranked[0]
    top_rank = rank_candidate(entry, top)
    runner_rank = rank_candidate(entry, ranked[1]) if len(ranked) > 1 else None
    if top_rank[0] != 1:
        return entry["key"], None, summaries
    if runner_rank is not None and runner_rank[:3] == top_rank[:3]:
        return entry["key"], None, summaries

    tmdb_type = "tv" if top["media_type"] == "tv" else "movie"
    details = tmdb_json(
        f"/{tmdb_type}/{top['id']}",
        token,
        {"append_to_response": "external_ids", "language": "en-US"},
    )
    imdb_id = details.get("external_ids", {}).get("imdb_id") or details.get("imdb_id")
    if not isinstance(imdb_id, str) or not re.fullmatch(r"tt\d+", imdb_id):
        return entry["key"], None, summaries
    release_value = details.get("first_air_date") if tmdb_type == "tv" else details.get("release_date")
    release_year = (
        int(release_value[:4])
        if isinstance(release_value, str) and len(release_value) >= 4 and release_value[:4].isdigit()
        else None
    )
    resolution = {
        "mediaType": "series" if tmdb_type == "tv" else "movie",
        "title": clean_text(details.get("name") or details.get("title") or entry["titles"][0]),
        **({"releaseYear": release_year} if release_year else {}),
        "tmdbId": top["id"],
        "imdbId": imdb_id,
        "method": "tmdb-title-and-media-review-candidate",
    }
    return entry["key"], resolution, summaries


def enrich_works(identity_map: dict, workers: int, limit: int | None) -> None:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise IdentityError(f"{TOKEN_ENV} is required for --tmdb")
    pending = [entry for entry in identity_map["works"] if not entry.get("resolution", {}).get("imdbId")]
    if limit is not None:
        pending = pending[:limit]
    results: dict[str, tuple[dict | None, list[dict]]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(enrich_work, entry, token): entry for entry in pending}
        for future in as_completed(futures):
            key, resolution, candidates = future.result()
            results[key] = (resolution, candidates)
    for entry in identity_map["works"]:
        if entry["key"] not in results:
            continue
        resolution, candidates = results[entry["key"]]
        if resolution is not None:
            entry["resolution"] = resolution
            entry.pop("candidates", None)
        else:
            entry["candidates"] = candidates


def apply_overrides(identity_map: dict) -> None:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise IdentityError(f"{TOKEN_ENV} is required for --apply-overrides")
    payload = load_json(OVERRIDES_PATH)
    overrides = payload.get("works")
    if not isinstance(overrides, list):
        raise IdentityError(f"{OVERRIDES_PATH}: works must be an array")
    by_key = {entry["key"]: entry for entry in identity_map["works"]}
    seen: set[str] = set()
    for override in overrides:
        if not isinstance(override, dict):
            raise IdentityError(f"{OVERRIDES_PATH}: invalid work override")
        key = override.get("key")
        media_type = override.get("mediaType")
        tmdb_id = override.get("tmdbId")
        if not isinstance(key, str) or key not in by_key:
            raise IdentityError(f"{OVERRIDES_PATH}: unknown work key {key!r}")
        if key in seen:
            raise IdentityError(f"{OVERRIDES_PATH}: duplicate work key {key!r}")
        seen.add(key)
        if media_type not in {"movie", "series"}:
            raise IdentityError(f"{OVERRIDES_PATH}: invalid media type for {key}")
        if not isinstance(tmdb_id, int) or tmdb_id <= 0:
            raise IdentityError(f"{OVERRIDES_PATH}: invalid TMDB ID for {key}")
        entry = by_key[key]
        existing_resolution = entry.get("resolution", {})
        if (
            existing_resolution.get("mediaType") == media_type
            and existing_resolution.get("tmdbId") == tmdb_id
            and isinstance(existing_resolution.get("imdbId"), str)
            and re.fullmatch(r"tt\d+", existing_resolution["imdbId"])
            and existing_resolution.get("method") == "reviewed-manual-override"
        ):
            note = override.get("reviewNote")
            if isinstance(note, str) and note.strip():
                entry["reviewNote"] = note.strip()
            entry.pop("candidates", None)
            continue
        tmdb_type = "tv" if media_type == "series" else "movie"
        details = tmdb_json(
            f"/{tmdb_type}/{tmdb_id}",
            token,
            {"append_to_response": "external_ids", "language": "en-US"},
        )
        tmdb_imdb_id = details.get("external_ids", {}).get("imdb_id") or details.get("imdb_id")
        override_imdb_id = override.get("imdbId")
        if override_imdb_id is not None and (
            not isinstance(override_imdb_id, str)
            or not re.fullmatch(r"tt\d+", override_imdb_id)
        ):
            raise IdentityError(f"{OVERRIDES_PATH}: invalid IMDb ID for {key}")
        if tmdb_imdb_id and override_imdb_id and tmdb_imdb_id != override_imdb_id:
            raise IdentityError(
                f"{OVERRIDES_PATH}: IMDb ID for {key} conflicts with TMDB {tmdb_type}/{tmdb_id}"
            )
        imdb_id = tmdb_imdb_id or override_imdb_id
        if not isinstance(imdb_id, str) or not re.fullmatch(r"tt\d+", imdb_id):
            raise IdentityError(f"TMDB {tmdb_type}/{tmdb_id} has no valid IMDb ID")
        release_value = (
            details.get("first_air_date") if media_type == "series" else details.get("release_date")
        )
        release_year = (
            int(release_value[:4])
            if isinstance(release_value, str)
            and len(release_value) >= 4
            and release_value[:4].isdigit()
            else None
        )
        entry["resolution"] = {
            "mediaType": media_type,
            "title": clean_text(details.get("name") or details.get("title") or entry["titles"][0]),
            **({"releaseYear": release_year} if release_year else {}),
            "tmdbId": tmdb_id,
            "imdbId": imdb_id,
            "method": "reviewed-manual-override",
        }
        note = override.get("reviewNote")
        if isinstance(note, str) and note.strip():
            entry["reviewNote"] = note.strip()
        entry.pop("candidates", None)


def validate_map(identity_map: dict) -> tuple[int, int, int, int]:
    work_count = len(identity_map.get("works", []))
    resolved_works = 0
    for entry in identity_map.get("works", []):
        resolution = entry.get("resolution")
        if not isinstance(resolution, dict):
            continue
        if (
            resolution.get("mediaType") in {"movie", "series", "podcast"}
            and isinstance(resolution.get("title"), str)
            and resolution["title"].strip()
            and (
                resolution.get("mediaType") == "podcast"
                or (
                    isinstance(resolution.get("tmdbId"), int)
                    and resolution["tmdbId"] > 0
                    and isinstance(resolution.get("imdbId"), str)
                    and re.fullmatch(r"tt\d+", resolution["imdbId"])
                )
            )
        ):
            if resolution.get("mediaType") != "podcast":
                release_year = resolution.get("releaseYear")
                if not isinstance(release_year, int):
                    raise IdentityError(f"{entry.get('key')}: resolved work has no release year")
                ceremony_years = entry.get("ceremonyYears", [])
                if not ceremony_years or any(not isinstance(year, int) for year in ceremony_years):
                    raise IdentityError(f"{entry.get('key')}: resolved work has invalid ceremony years")
                if release_year > min(ceremony_years) and not (
                    resolution.get("method") == "reviewed-manual-override"
                    and isinstance(entry.get("reviewNote"), str)
                    and entry["reviewNote"].strip()
                ):
                    raise IdentityError(
                        f"{entry.get('key')}: release year {release_year} follows its earliest "
                        "ceremony without a reviewed override"
                    )
            resolved_works += 1
    people_count = len(identity_map.get("people", []))
    resolved_people = sum(
        1
        for entry in identity_map.get("people", [])
        if isinstance(entry.get("resolution"), dict)
        and (entry["resolution"].get("tmdbId") or entry["resolution"].get("imdbId"))
    )
    return work_count, resolved_works, people_count, resolved_people


def write_map(identity_map: dict) -> None:
    IDENTITY_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDENTITY_MAP_PATH.write_text(
        json.dumps(identity_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--tmdb", action="store_true")
    parser.add_argument("--apply-overrides", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if not (args.seed or args.tmdb or args.apply_overrides or args.check):
        parser.error("choose --seed, --tmdb, --apply-overrides, or --check")
    try:
        snapshot = load_json(SNAPSHOT_PATH)
        categories = load_json(CATEGORIES_PATH)
        existing = load_json(IDENTITY_MAP_PATH) if IDENTITY_MAP_PATH.exists() else None
        identity_map = build_seed(snapshot, categories, existing)
        if (
            args.check
            and existing is not None
            and existing.get("snapshotSha256") != identity_map["snapshotSha256"]
        ):
            raise IdentityError("committed identity map does not match the official snapshot")
        if args.tmdb:
            enrich_works(identity_map, args.workers, args.limit)
        if args.apply_overrides:
            apply_overrides(identity_map)
        work_count, resolved_works, people_count, resolved_people = validate_map(identity_map)
        if args.seed or args.tmdb or args.apply_overrides:
            write_map(identity_map)
        print(
            "Golden Globes identity map: "
            f"{resolved_works}/{work_count} works resolved; "
            f"{resolved_people}/{people_count} people reused from canonical identities; "
            f"{identity_map['matchedCurrentCategoryWinnerRecords']} current-lineage winner records."
        )
        if args.check and resolved_works != work_count:
            raise IdentityError(f"{work_count - resolved_works} work identities remain unresolved")
        return 0
    except IdentityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
