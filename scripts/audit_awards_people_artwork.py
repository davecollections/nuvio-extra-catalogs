#!/usr/bin/env python3
"""Build an actor/director artwork handoff from reviewed award identities.

Use --write --people-commit SHA for a new audit; --check reproduces the report
against its immutable People manifest. Unresolved people are never artwork jobs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from bafta_common import SOURCE_DIR, current_programme_for_category, load_json, selected_winners
from build_bafta_identity_seed import recipient_key
from check_people_artwork_integration import (
    CORE_ASSET_KEYS, FOCUS_ASSET_KEYS, RUNTIME_MANIFEST_URL,
    load_manifest_bytes, validate_people_manifest,
)
from enrich_bafta_people import validate as validate_bafta_people

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "awards-actor-director-artwork.json"
HANDOFF = REPORT.with_suffix(".md")
ROLES = {"actor", "director"}


def inventory() -> tuple[list[dict], list[dict], str]:
    people: dict[int, dict] = {}
    unresolved: dict[str, dict] = {}
    digest = hashlib.sha256()

    def read(path: Path) -> dict:
        raw = path.read_bytes()
        # Canonical JSON hashing is independent of checkout line endings.
        value = json.loads(raw)
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(json.dumps(value, ensure_ascii=False, sort_keys=True).encode())
        return value

    def add(key: str, name: str, role: str, identity: dict, context: dict) -> None:
        person_id = identity.get("tmdbId")
        if person_id is None:
            entry = unresolved.setdefault(key, {
                "name": name, "imdbPersonId": identity.get("imdbId"),
                "roles": [], "awardContexts": [],
            })
        else:
            if not isinstance(person_id, int) or person_id <= 0:
                raise ValueError(f"Invalid TMDB person ID: {key}")
            entry = people.setdefault(person_id, {
                "name": name, "tmdbPersonId": person_id,
                "imdbPersonIds": [], "roles": [], "awardContexts": [],
            })
            if identity.get("imdbId") and identity["imdbId"] not in entry["imdbPersonIds"]:
                entry["imdbPersonIds"].append(identity["imdbId"])
        if role not in entry["roles"]:
            entry["roles"].append(role)
        if context not in entry["awardContexts"]:
            entry["awardContexts"].append(context)

    for body in sorted((ROOT / "data" / "awards").iterdir()):
        if not body.is_dir() or body.name.startswith("bafta-"):
            continue
        categories = {c["id"]: c for c in read(body / "categories.json")["categories"]}
        for path in sorted((body / "results").glob("*.json")):
            payload = read(path)
            for result in payload["results"]:
                category = categories[result["categoryId"]]
                role = category.get("creditRole")
                if role not in ROLES or result.get("status") != "winner":
                    continue
                for person in result.get("people", []):
                    context = {"awardBodyId": body.name, "categoryId": category["id"],
                               "year": payload["ceremony"]["year"]}
                    add(f"{body.name}:{person.get('imdbId') or person['name']}",
                        person["name"], role, person, context)

    identity_map = read(SOURCE_DIR / "identity-map.json")
    read(SOURCE_DIR / "category-definitions.json")
    validate_bafta_people(identity_map)
    recipients = {p["key"]: p for p in identity_map["recipients"]}
    for winner in selected_winners():
        role = winner["category"].get("creditRole")
        if role not in ROLES:
            continue
        for name in winner["recipientValues"]:
            key = recipient_key(name, winner["nominationId"])
            context = {"awardBodyId": "bafta-" + current_programme_for_category(winner["category"]["id"]),
                       "categoryId": winner["category"]["id"], "year": winner["year"],
                       "sourceRecordId": winner["nominationId"]}
            add(key, name, role, recipients[key].get("resolution", {}), context)
    for entry in [*people.values(), *unresolved.values()]:
        entry["roles"].sort()
        entry["awardContexts"].sort(key=lambda c: (c["awardBodyId"], c["categoryId"], c["year"]))
        if "imdbPersonIds" in entry:
            entry["imdbPersonIds"].sort()
    return (sorted(people.values(), key=lambda p: (p["name"].casefold(), p["tmdbPersonId"])),
            sorted(unresolved.values(), key=lambda p: p["name"].casefold()), digest.hexdigest())


def build_report(raw: bytes, commit: str, checked_at: str) -> dict:
    assets, _ = validate_people_manifest(json.loads(raw))
    people, unresolved, source_hash = inventory()
    missing, membership, focus = [], [], []
    for person in people:
        record = assets.get(person["tmdbPersonId"])
        if record is None:
            missing.append({**person, "missingAssets": list(CORE_ASSET_KEYS + FOCUS_ASSET_KEYS)})
            continue
        missing_roles = sorted(set(person["roles"]) - set(record["categoryMembership"]))
        if missing_roles:
            membership.append({**person, "missingMemberships": missing_roles,
                               "existingMemberships": record["categoryMembership"]})
        missing_focus = [key for key in FOCUS_ASSET_KEYS if key not in record["assets"]]
        if missing_focus:
            focus.append({**person, "missingAssets": missing_focus})
    return {
        "schemaVersion": 1, "checkedAt": checked_at,
        "scope": "Reviewed actor/director winner identities in Academy, Golden Globes, and all three BAFTA programmes; current included work-associated lineages only.",
        "verification": "Manifest identity, membership and asset descriptors. Individual asset URLs are not fetched by this audit.",
        "inputSha256": source_hash,
        "peopleManifest": {"commit": commit, "sha256": hashlib.sha256(raw).hexdigest(),
                           "url": RUNTIME_MANIFEST_URL.replace("/main/", f"/{commit}/")},
        "summary": {"verifiedPeople": len(people), "presentInManifest": len(people)-len(missing),
                    "missingPeople": len(missing), "membershipGaps": len(membership),
                    "missingFocusPairs": len(focus), "unresolvedIdentityUnits": len(unresolved)},
        "missingPeople": missing, "membershipGaps": membership, "missingFocusPairs": focus,
        "unresolvedIdentities": unresolved, "reviewedPeople": people,
    }


def markdown(report: dict) -> str:
    summary = report["summary"]
    lines = ["# Awards actor/director artwork handoff", "", "Issue: #41", "",
             f"Reviewed {report['checkedAt']} against People commit `{report['peopleManifest']['commit']}`.", "",
             report["scope"], "", report["verification"], "",
             f"Verified people: **{summary['verifiedPeople']}**; present: **{summary['presentInManifest']}**; missing: **{summary['missingPeople']}**; membership gaps: **{summary['membershipGaps']}**; focus-pair gaps: **{summary['missingFocusPairs']}**.", "",
             "Use TMDB Person ID as the asset identity. Reuse existing artwork when adding membership. Actor and director roles for one person share one asset directory. Do not generate artwork for unresolved identities.", "",
             "Movie/series catalogues do not require People artwork; this handoff supports native PERSON/DIRECTOR collections.", ""]
    for title, field in [("New artwork sets", "missingPeople"), ("Membership changes", "membershipGaps"),
                         ("Optional focus-pair additions", "missingFocusPairs")]:
        lines += [f"## {title}", "", "| Person | TMDB Person ID | Roles | Action |", "| --- | ---: | --- | --- |"]
        for person in report[field]:
            actions = person.get("missingAssets") or person.get("missingMemberships", [])
            name = person["name"].replace("|", "\\|")
            lines.append(f"| {name} | [{person['tmdbPersonId']}](https://www.themoviedb.org/person/{person['tmdbPersonId']}) | {', '.join(person['roles'])} | {', '.join(actions)} |")
        if not report[field]:
            lines.append("| None | | | |")
        lines.append("")
    lines += ["## Identity research still required", "",
              f"**{summary['unresolvedIdentityUnits']} identity units** remain unresolved. These are not confirmed artwork gaps; some may already have assets under an unlinked ID.", "",
              "| Source name | Roles | Award bodies |", "| --- | --- | --- |"]
    for person in report["unresolvedIdentities"]:
        bodies = sorted({c["awardBodyId"] for c in person["awardContexts"]})
        lines.append(f"| {person['name'].replace('|', '/')} | {', '.join(person['roles'])} | {', '.join(bodies)} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--people-commit")
    args = parser.parse_args()
    previous = load_json(REPORT) if args.check else None
    commit = previous["peopleManifest"]["commit"] if previous else args.people_commit
    if not commit or not re.fullmatch(r"[a-f0-9]{40}", commit):
        parser.error("--write requires a full immutable --people-commit SHA")
    raw = load_manifest_bytes(RUNTIME_MANIFEST_URL.replace("/main/", f"/{commit}/"))
    report = build_report(raw, commit, previous["checkedAt"] if previous else date.today().isoformat())
    if previous and report["peopleManifest"]["sha256"] != previous["peopleManifest"]["sha256"]:
        raise ValueError("Pinned People manifest bytes changed")
    outputs = {REPORT: json.dumps(report, ensure_ascii=False, indent=2) + "\n", HANDOFF: markdown(report)}
    for path, content in outputs.items():
        if args.write:
            path.write_text(content, encoding="utf-8")
        elif not path.is_file() or path.read_text(encoding="utf-8") != content:
            raise ValueError(f"Stale artwork audit: {path}")
    print(json.dumps(report["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
