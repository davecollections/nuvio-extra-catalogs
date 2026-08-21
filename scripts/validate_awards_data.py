#!/usr/bin/env python3
"""Validate canonical awards data independently of generated catalogue outputs."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
AWARDS_ROOT = REPO_ROOT / "data" / "awards"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FILE_RE = re.compile(r"^(?P<number>\d{3})-(?P<year>\d{4})\.json$")
IMDB_RE = re.compile(r"^tt\d+$")
IMDB_PERSON_RE = re.compile(r"^nm\d+$")
MEDIA_TYPES = {"movie", "series"}
CATEGORY_MEDIA_TYPES = MEDIA_TYPES | {"mixed"}
RECIPIENT_KINDS = {"work", "person", "team", "other"}
CREDIT_ROLES = {
    "actor",
    "director",
    "producer",
    "writer",
    "composer",
    "cinematographer",
    "editor",
    "other",
}
STATUSES = {"winner", "nominee"}


class ValidationError(RuntimeError):
    pass


@dataclass
class Summary:
    award_bodies: int = 0
    categories: int = 0
    ceremonies: int = 0
    results: int = 0
    work_links: int = 0
    person_links: int = 0
    sources: set[tuple[str, str]] = field(default_factory=set)


@dataclass
class IdentityRegistry:
    works_by_tmdb: dict[tuple[str, int], tuple[str, str | None]] = field(default_factory=dict)
    works_by_imdb: dict[str, tuple[str, str, int | None]] = field(default_factory=dict)
    imdb_by_tmdb: dict[tuple[str, int], str] = field(default_factory=dict)
    people_by_tmdb: dict[int, str] = field(default_factory=dict)
    people_by_imdb: dict[str, tuple[str, int | None]] = field(default_factory=dict)
    imdb_by_person_tmdb: dict[int, str] = field(default_factory=dict)


def fail(path: Path, message: str) -> None:
    raise ValidationError(f"{path}: {message}")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        fail(path, "top-level JSON value must be an object")
    return value


def require_keys(path: Path, value: dict, required: set[str], allowed: set[str], label: str) -> None:
    missing = sorted(required - value.keys())
    extra = sorted(value.keys() - allowed)
    if missing:
        fail(path, f"{label} is missing required keys: {missing}")
    if extra:
        fail(path, f"{label} has unsupported keys: {extra}")


def require_nonempty_string(path: Path, value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(path, f"{label} must be a non-empty string")
    return value.strip()


def require_slug(path: Path, value: object, label: str) -> str:
    text = require_nonempty_string(path, value, label)
    if not SLUG_RE.fullmatch(text):
        fail(path, f"{label} must be a stable lowercase slug")
    return text


def require_positive_int(path: Path, value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        fail(path, f"{label} must be a positive integer")
    return value


def validate_reference(path: Path, value: object, label: str) -> str:
    reference = require_nonempty_string(path, value, label)
    parsed = urlparse(reference)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        fail(path, f"{label} must be an absolute HTTP(S) URL")
    return reference


def validate_checked_at(path: Path, value: object) -> str:
    checked_at = require_nonempty_string(path, value, "source.checkedAt")
    try:
        checked_date = date.fromisoformat(checked_at)
    except ValueError as exc:
        raise ValidationError(f"{path}: source.checkedAt must use YYYY-MM-DD") from exc
    if checked_date > date.today():
        fail(path, "source.checkedAt cannot be in the future")
    return checked_at


def validate_award_registry(
    path: Path, expected_id: str
) -> tuple[dict, tuple[int, int], set[tuple[str, str]]]:
    value = load_json(path)
    require_keys(
        path,
        value,
        {"schemaVersion", "id", "name", "authoritativeSources", "ceremonyCoverage"},
        {
            "schemaVersion",
            "id",
            "name",
            "organization",
            "externalIds",
            "authoritativeSources",
            "ceremonyCoverage",
        },
        "award registry",
    )
    if value["schemaVersion"] != 1:
        fail(path, "schemaVersion must be 1")
    award_body_id = require_slug(path, value["id"], "id")
    if award_body_id != expected_id:
        fail(path, f"id {award_body_id!r} must match directory name {expected_id!r}")
    require_nonempty_string(path, value["name"], "name")
    if "organization" in value:
        require_nonempty_string(path, value["organization"], "organization")

    external_ids = value.get("externalIds")
    if external_ids is not None:
        if not isinstance(external_ids, dict):
            fail(path, "externalIds must be an object")
        require_keys(path, external_ids, set(), {"tmdbAwardId"}, "externalIds")
        if "tmdbAwardId" in external_ids:
            require_positive_int(path, external_ids["tmdbAwardId"], "externalIds.tmdbAwardId")

    raw_sources = value["authoritativeSources"]
    if not isinstance(raw_sources, list) or not raw_sources:
        fail(path, "authoritativeSources must be a non-empty array")
    authorities: set[tuple[str, str]] = set()
    for index, raw_source in enumerate(raw_sources):
        if not isinstance(raw_source, dict):
            fail(path, f"authoritativeSources[{index}] must be an object")
        require_keys(
            path,
            raw_source,
            {"name", "reference"},
            {"name", "reference"},
            f"authoritativeSources[{index}]",
        )
        authority = (
            require_nonempty_string(path, raw_source["name"], "authoritative source name"),
            validate_reference(path, raw_source["reference"], "authoritative source reference"),
        )
        if authority in authorities:
            fail(path, f"duplicate authoritative source {authority[0]!r}")
        authorities.add(authority)

    coverage = value["ceremonyCoverage"]
    if not isinstance(coverage, dict):
        fail(path, "ceremonyCoverage must be an object")
    require_keys(
        path,
        coverage,
        {"firstCeremonyNumber", "lastCeremonyNumber"},
        {"firstCeremonyNumber", "lastCeremonyNumber"},
        "ceremonyCoverage",
    )
    first = require_positive_int(path, coverage["firstCeremonyNumber"], "firstCeremonyNumber")
    last = require_positive_int(path, coverage["lastCeremonyNumber"], "lastCeremonyNumber")
    if last < first:
        fail(path, "lastCeremonyNumber cannot precede firstCeremonyNumber")
    return value, (first, last), authorities


def validate_category_registry(path: Path, award_body_id: str) -> dict[str, dict]:
    value = load_json(path)
    require_keys(
        path,
        value,
        {"schemaVersion", "awardBodyId", "categories"},
        {"schemaVersion", "awardBodyId", "categories"},
        "category registry",
    )
    if value["schemaVersion"] != 1:
        fail(path, "schemaVersion must be 1")
    if value["awardBodyId"] != award_body_id:
        fail(path, "awardBodyId must match award.json")
    raw_categories = value["categories"]
    if not isinstance(raw_categories, list) or not raw_categories:
        fail(path, "categories must be a non-empty array")

    categories: dict[str, dict] = {}
    for index, category in enumerate(raw_categories):
        label = f"categories[{index}]"
        if not isinstance(category, dict):
            fail(path, f"{label} must be an object")
        require_keys(
            path,
            category,
            {"id", "name", "mediaType", "recipientKind"},
            {"id", "name", "aliases", "mediaType", "recipientKind", "creditRole", "externalIds"},
            label,
        )
        category_id = require_slug(path, category["id"], f"{label}.id")
        if category_id in categories:
            fail(path, f"duplicate category ID {category_id!r}")
        require_nonempty_string(path, category["name"], f"{label}.name")
        if not isinstance(category["mediaType"], str) or category["mediaType"] not in CATEGORY_MEDIA_TYPES:
            fail(path, f"{label}.mediaType is invalid")
        if not isinstance(category["recipientKind"], str) or category["recipientKind"] not in RECIPIENT_KINDS:
            fail(path, f"{label}.recipientKind is invalid")
        if "creditRole" in category and (
            not isinstance(category["creditRole"], str)
            or category["creditRole"] not in CREDIT_ROLES
        ):
            fail(path, f"{label}.creditRole is invalid")

        aliases = category.get("aliases", [])
        if not isinstance(aliases, list):
            fail(path, f"{label}.aliases must be an array")
        normalized_aliases = [
            require_nonempty_string(path, alias, f"{label}.aliases") for alias in aliases
        ]
        if len(set(normalized_aliases)) != len(normalized_aliases):
            fail(path, f"{label}.aliases contains duplicates")

        external_ids = category.get("externalIds")
        if external_ids is not None:
            if not isinstance(external_ids, dict):
                fail(path, f"{label}.externalIds must be an object")
            require_keys(path, external_ids, set(), {"tmdbCategoryId"}, f"{label}.externalIds")
            if "tmdbCategoryId" in external_ids:
                require_positive_int(
                    path, external_ids["tmdbCategoryId"], f"{label}.externalIds.tmdbCategoryId"
                )
        categories[category_id] = category
    return categories


def register_work(path: Path, work: dict, identities: IdentityRegistry) -> None:
    media_type = work["mediaType"]
    title = work["title"]
    tmdb_id = work.get("tmdbId")
    imdb_id = work.get("imdbId")

    if tmdb_id is not None:
        key = (media_type, tmdb_id)
        value = (title, imdb_id)
        existing = identities.works_by_tmdb.get(key)
        if existing is not None and existing[0] != title:
            fail(path, f"TMDB {media_type} ID {tmdb_id} maps to both {existing[0]!r} and {title!r}")
        identities.works_by_tmdb[key] = value
        if imdb_id is not None:
            existing_imdb = identities.imdb_by_tmdb.get(key)
            if existing_imdb is not None and existing_imdb != imdb_id:
                fail(path, f"TMDB {media_type} ID {tmdb_id} maps to multiple IMDb IDs")
            identities.imdb_by_tmdb[key] = imdb_id

    if imdb_id is not None:
        value = (media_type, title, tmdb_id)
        existing = identities.works_by_imdb.get(imdb_id)
        if existing is not None and (existing[0] != media_type or existing[1] != title):
            fail(path, f"IMDb ID {imdb_id} maps to conflicting work identities")
        if existing is not None and existing[2] is not None and tmdb_id is not None and existing[2] != tmdb_id:
            fail(path, f"IMDb ID {imdb_id} maps to multiple TMDB IDs")
        if existing is not None and tmdb_id is None:
            value = (media_type, title, existing[2])
        identities.works_by_imdb[imdb_id] = value


def validate_work(path: Path, raw_work: object, category: dict, identities: IdentityRegistry) -> tuple:
    if not isinstance(raw_work, dict):
        fail(path, "work relationship must be an object")
    require_keys(
        path,
        raw_work,
        {"mediaType", "title"},
        {"mediaType", "title", "releaseYear", "tmdbId", "imdbId"},
        "work",
    )
    media_type = raw_work["mediaType"]
    if media_type not in MEDIA_TYPES:
        fail(path, "work.mediaType must be movie or series")
    if category["mediaType"] != "mixed" and media_type != category["mediaType"]:
        fail(path, f"work.mediaType {media_type!r} conflicts with category mediaType")
    title = require_nonempty_string(path, raw_work["title"], "work.title")
    raw_work["title"] = title

    release_year = raw_work.get("releaseYear")
    if release_year is not None and (
        not isinstance(release_year, int)
        or isinstance(release_year, bool)
        or not 1800 <= release_year <= 2200
    ):
        fail(path, "work.releaseYear must be an integer from 1800 through 2200")
    tmdb_id = raw_work.get("tmdbId")
    if tmdb_id is not None:
        tmdb_id = require_positive_int(path, tmdb_id, "work.tmdbId")
    imdb_id = raw_work.get("imdbId")
    if imdb_id is not None and (not isinstance(imdb_id, str) or not IMDB_RE.fullmatch(imdb_id)):
        fail(path, "work.imdbId must match ^tt[0-9]+$")

    register_work(path, raw_work, identities)
    identity = (
        media_type,
        ("tmdb", tmdb_id)
        if tmdb_id is not None
        else ("imdb", imdb_id)
        if imdb_id is not None
        else ("text", title.casefold(), release_year),
    )
    return identity


def validate_person(path: Path, raw_person: object, identities: IdentityRegistry) -> tuple:
    if not isinstance(raw_person, dict):
        fail(path, "person relationship must be an object")
    require_keys(path, raw_person, {"name"}, {"name", "tmdbId", "imdbId"}, "person")
    name = require_nonempty_string(path, raw_person["name"], "person.name")
    raw_person["name"] = name
    tmdb_id = raw_person.get("tmdbId")
    if tmdb_id is not None:
        tmdb_id = require_positive_int(path, tmdb_id, "person.tmdbId")
        existing = identities.people_by_tmdb.get(tmdb_id)
        if existing is not None and existing != name:
            fail(path, f"TMDB Person ID {tmdb_id} maps to both {existing!r} and {name!r}")
        identities.people_by_tmdb[tmdb_id] = name
    imdb_id = raw_person.get("imdbId")
    if imdb_id is not None:
        if not isinstance(imdb_id, str) or not IMDB_PERSON_RE.fullmatch(imdb_id):
            fail(path, "person.imdbId must match ^nm[0-9]+$")
        existing = identities.people_by_imdb.get(imdb_id)
        if existing is not None and existing[0] != name:
            fail(path, f"IMDb Person ID {imdb_id} maps to both {existing[0]!r} and {name!r}")
        if existing is not None and existing[1] is not None and tmdb_id is not None and existing[1] != tmdb_id:
            fail(path, f"IMDb Person ID {imdb_id} maps to multiple TMDB Person IDs")
        identities.people_by_imdb[imdb_id] = (name, tmdb_id if tmdb_id is not None else existing[1] if existing else None)
        if tmdb_id is not None:
            existing_imdb = identities.imdb_by_person_tmdb.get(tmdb_id)
            if existing_imdb is not None and existing_imdb != imdb_id:
                fail(path, f"TMDB Person ID {tmdb_id} maps to multiple IMDb Person IDs")
            identities.imdb_by_person_tmdb[tmdb_id] = imdb_id
    if tmdb_id is not None:
        return ("tmdb", tmdb_id)
    if imdb_id is not None:
        return ("imdb", imdb_id)
    return ("text", name.casefold())


def validate_source(
    path: Path,
    raw_source: object,
    authorities: set[tuple[str, str]],
    summary: Summary,
) -> None:
    if not isinstance(raw_source, dict):
        fail(path, "source must be an object")
    require_keys(
        path,
        raw_source,
        {"name", "reference", "checkedAt"},
        {"name", "reference", "checkedAt"},
        "source",
    )
    name = require_nonempty_string(path, raw_source["name"], "source.name")
    reference = validate_reference(path, raw_source["reference"], "source.reference")
    validate_checked_at(path, raw_source["checkedAt"])
    if (name, reference) not in authorities:
        fail(path, f"source {name!r} is not declared in award.json authoritativeSources")
    summary.sources.add((name, reference))


def validate_result(
    path: Path,
    raw_result: object,
    categories: dict[str, dict],
    identities: IdentityRegistry,
    summary: Summary,
) -> tuple:
    if not isinstance(raw_result, dict):
        fail(path, "result must be an object")
    require_keys(
        path,
        raw_result,
        {"categoryId", "status"},
        {"categoryId", "status", "work", "works", "people", "recipientLabel", "note"},
        "result",
    )
    category_id = require_slug(path, raw_result["categoryId"], "result.categoryId")
    category = categories.get(category_id)
    if category is None:
        fail(path, f"result references unknown category {category_id!r}")
    status = raw_result["status"]
    if status not in STATUSES:
        fail(path, "result.status must be winner or nominee")

    has_work = "work" in raw_result
    has_works = "works" in raw_result
    if has_work and has_works:
        fail(path, "result must contain at most one of work or works")

    work_identities: list[tuple] = []
    if has_work:
        work_identities.append(validate_work(path, raw_result["work"], category, identities))
    elif has_works:
        works = raw_result["works"]
        if not isinstance(works, list) or not works:
            fail(path, "result.works must be a non-empty array")
        for raw_work in works:
            work_identities.append(validate_work(path, raw_work, category, identities))

    raw_people = raw_result.get("people", [])
    if not isinstance(raw_people, list):
        fail(path, "result.people must be an array")
    person_identities = [validate_person(path, person, identities) for person in raw_people]

    recipient_label = raw_result.get("recipientLabel")
    if recipient_label is not None:
        recipient_label = require_nonempty_string(path, recipient_label, "result.recipientLabel")
    note = raw_result.get("note")
    if note is not None:
        require_nonempty_string(path, note, "result.note")

    if not work_identities and not person_identities and recipient_label is None:
        fail(path, "result must preserve at least one work, person, or recipientLabel relationship")
    if category["recipientKind"] == "work" and not work_identities:
        fail(path, f"work-recipient category {category_id!r} requires work or works")
    if category["recipientKind"] == "person" and not person_identities:
        fail(path, f"person-recipient category {category_id!r} requires people")

    summary.results += 1
    summary.work_links += len(work_identities)
    summary.person_links += len(person_identities)
    return (
        category_id,
        status,
        tuple(sorted(work_identities, key=repr)),
        tuple(sorted(person_identities, key=repr)),
        recipient_label,
    )


def validate_ceremony_file(
    path: Path,
    award_body_id: str,
    categories: dict[str, dict],
    authorities: set[tuple[str, str]],
    identities: IdentityRegistry,
    summary: Summary,
) -> tuple[int, int]:
    match = FILE_RE.fullmatch(path.name)
    if not match:
        fail(path, "filename must use NNN-YYYY.json ceremony-number/year format")
    expected_number = int(match.group("number"))
    expected_year = int(match.group("year"))
    value = load_json(path)
    require_keys(
        path,
        value,
        {"schemaVersion", "awardBodyId", "ceremony", "source", "results"},
        {"$schema", "schemaVersion", "awardBodyId", "ceremony", "source", "results"},
        "ceremony file",
    )
    if value["schemaVersion"] != 1:
        fail(path, "schemaVersion must be 1")
    if value["awardBodyId"] != award_body_id:
        fail(path, "awardBodyId must match award.json")

    ceremony = value["ceremony"]
    if not isinstance(ceremony, dict):
        fail(path, "ceremony must be an object")
    require_keys(path, ceremony, {"year", "number"}, {"year", "number", "date"}, "ceremony")
    number = require_positive_int(path, ceremony["number"], "ceremony.number")
    year = ceremony["year"]
    if not isinstance(year, int) or isinstance(year, bool) or not 1800 <= year <= 2200:
        fail(path, "ceremony.year must be an integer from 1800 through 2200")
    if number != expected_number or year != expected_year:
        fail(path, f"filename {expected_number}/{expected_year} does not match ceremony {number}/{year}")
    if "date" in ceremony:
        try:
            date.fromisoformat(require_nonempty_string(path, ceremony["date"], "ceremony.date"))
        except ValueError as exc:
            raise ValidationError(f"{path}: ceremony.date must use YYYY-MM-DD") from exc

    validate_source(path, value["source"], authorities, summary)
    results = value["results"]
    if not isinstance(results, list):
        fail(path, "results must be an array")
    fingerprints: set[tuple] = set()
    for raw_result in results:
        fingerprint = validate_result(path, raw_result, categories, identities, summary)
        if fingerprint in fingerprints:
            fail(path, f"duplicate canonical relationship for {fingerprint[0]!r}/{fingerprint[1]!r}")
        fingerprints.add(fingerprint)
    summary.ceremonies += 1
    return number, year


def validate_award_body(body_dir: Path, identities: IdentityRegistry, summary: Summary) -> None:
    award_body_id = require_slug(body_dir, body_dir.name, "award-body directory")
    _, coverage, authorities = validate_award_registry(body_dir / "award.json", award_body_id)
    categories = validate_category_registry(body_dir / "categories.json", award_body_id)
    results_dir = body_dir / "results"
    if not results_dir.is_dir():
        fail(results_dir, "results directory is missing")
    files = sorted(results_dir.glob("*.json"))
    if not files:
        fail(results_dir, "no ceremony files found")

    ceremonies: dict[int, int] = {}
    for path in files:
        number, year = validate_ceremony_file(
            path, award_body_id, categories, authorities, identities, summary
        )
        if number in ceremonies:
            fail(path, f"duplicate ceremony number {number}")
        ceremonies[number] = year

    first, last = coverage
    expected_numbers = set(range(first, last + 1))
    actual_numbers = set(ceremonies)
    if actual_numbers != expected_numbers:
        missing = sorted(expected_numbers - actual_numbers)
        extra = sorted(actual_numbers - expected_numbers)
        fail(
            results_dir,
            f"ceremonyCoverage mismatch; missing={missing}, extra={extra}",
        )

    summary.award_bodies += 1
    summary.categories += len(categories)


def validate_repository() -> Summary:
    if not AWARDS_ROOT.is_dir():
        fail(AWARDS_ROOT, "awards data directory is missing")
    body_dirs = sorted(path for path in AWARDS_ROOT.iterdir() if path.is_dir())
    if not body_dirs:
        fail(AWARDS_ROOT, "no award-body directories found")

    identities = IdentityRegistry()
    summary = Summary()
    for body_dir in body_dirs:
        validate_award_body(body_dir, identities, summary)
    return summary


def main() -> int:
    try:
        summary = validate_repository()
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "Awards data is valid: "
        f"{summary.award_bodies} award body, "
        f"{summary.categories} categories, "
        f"{summary.ceremonies} ceremonies, "
        f"{summary.results} results, "
        f"{summary.work_links} work links, "
        f"{summary.person_links} person links, "
        f"{len(summary.sources)} authoritative source reference(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
