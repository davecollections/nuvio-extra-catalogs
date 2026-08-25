#!/usr/bin/env python3
"""Build the deterministic BAFTA work and credited-recipient identity inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from bafta_common import (
    DEFINITIONS_PATH,
    DECISIONS_PATH,
    SNAPSHOTS,
    SOURCE_DIR,
    load_json,
    selected_winners,
    work_key,
)
from enrich_golden_globes_identities import normalized_title


IDENTITY_MAP_PATH = SOURCE_DIR / "identity-map.json"
GENERIC_RECIPIENTS = {
    "camerateam",
    "designteam",
    "developmentteam",
    "productionteam",
    "soundteam",
    "sportteam",
    "team",
}


def input_digest() -> str:
    digest = hashlib.sha256()
    paths = [DEFINITIONS_PATH, DECISIONS_PATH, *SNAPSHOTS.values()]
    for path in paths:
        value = load_json(path)
        digest.update(path.relative_to(SOURCE_DIR).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\0")
    return digest.hexdigest()


def append_unique(entry: dict, field: str, value: object) -> None:
    if value not in entry[field]:
        entry[field].append(value)


def recipient_key(name: str, nomination_id: str) -> str:
    normalized = normalized_title(name)
    if normalized in GENERIC_RECIPIENTS or normalized.endswith("team"):
        return f"label:{nomination_id}:{normalized}"
    return f"recipient:{normalized}"


def existing_review_fields(existing: dict | None, field: str) -> dict[str, dict]:
    if existing is None:
        return {}
    preserved: dict[str, dict] = {}
    for entry in existing.get(field, []):
        key = entry.get("key")
        if not isinstance(key, str):
            continue
        fields = {
            name: entry[name]
            for name in ("resolution", "candidates", "reviewNote", "reviewOutcome")
            if name in entry
        }
        if fields:
            preserved[key] = fields
    return preserved


def build_seed(existing: dict | None) -> dict:
    work_review = existing_review_fields(existing, "works")
    recipient_review = existing_review_fields(existing, "recipients")
    works: dict[str, dict] = {}
    recipients: dict[str, dict] = {}
    selected_nominations: set[tuple[str, str]] = set()
    selected_work_links = 0
    snapshot_dates = []
    for snapshot_path in SNAPSHOTS.values():
        snapshot_dates.append(load_json(snapshot_path)["checkedAt"])

    for selected in selected_winners():
        selected_nominations.add((selected["programme"], selected["nominationId"]))
        selected_work_links += 1
        category = selected["category"]
        key = work_key(selected)
        work = works.setdefault(
            key,
            {
                "key": key,
                "titles": [],
                "programmes": [],
                "years": [],
                "categoryIds": [],
                "nominationIds": [],
                "mediaScope": category["mediaType"],
            },
        )
        append_unique(work, "titles", selected["workTitle"])
        append_unique(work, "programmes", selected["programme"])
        append_unique(work, "years", selected["year"])
        append_unique(work, "categoryIds", category["id"])
        append_unique(work, "nominationIds", selected["nominationId"])

        for value in selected["recipientValues"]:
            recipient_id = recipient_key(value, selected["nominationId"])
            recipient = recipients.setdefault(
                recipient_id,
                {
                    "key": recipient_id,
                    "names": [],
                    "programmes": [],
                    "years": [],
                    "categoryIds": [],
                    "creditRoles": [],
                    "nominationIds": [],
                },
            )
            append_unique(recipient, "names", value)
            append_unique(recipient, "programmes", selected["programme"])
            append_unique(recipient, "years", selected["year"])
            append_unique(recipient, "categoryIds", category["id"])
            append_unique(recipient, "creditRoles", category.get("creditRole", "other"))
            append_unique(recipient, "nominationIds", selected["nominationId"])

    work_entries = []
    for key in sorted(works):
        entry = works[key]
        for field in ("programmes", "years", "categoryIds", "nominationIds"):
            entry[field].sort()
        entry.update(work_review.get(key, {}))
        work_entries.append(entry)

    recipient_entries = []
    for key in sorted(recipients):
        entry = recipients[key]
        for field in (
            "programmes",
            "years",
            "categoryIds",
            "creditRoles",
            "nominationIds",
        ):
            entry[field].sort()
        entry.update(recipient_review.get(key, {}))
        recipient_entries.append(entry)

    return {
        "schemaVersion": 1,
        "sourceCheckedAt": max(snapshot_dates),
        "inputSha256": input_digest(),
        "selectedWinnerRecords": len(selected_nominations),
        "selectedWorkLinks": selected_work_links,
        "works": work_entries,
        "recipients": recipient_entries,
    }


def serialized(seed: dict) -> str:
    return json.dumps(seed, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        parser.error("choose --write or --check")
    try:
        existing = load_json(IDENTITY_MAP_PATH) if IDENTITY_MAP_PATH.is_file() else None
        content = serialized(build_seed(existing))
        if args.write:
            IDENTITY_MAP_PATH.write_text(content, encoding="utf-8")
        if args.check:
            if not IDENTITY_MAP_PATH.is_file() or IDENTITY_MAP_PATH.read_text(encoding="utf-8") != content:
                raise ValueError("BAFTA identity map seed is stale")
        seed = json.loads(content)
        resolved_works = sum("resolution" in entry for entry in seed["works"])
        resolved_recipients = sum("resolution" in entry for entry in seed["recipients"])
        print(
            "BAFTA identity seed: "
            f"{seed['selectedWinnerRecords']} selected records, "
            f"{seed['selectedWorkLinks']} work links, {len(seed['works'])} works "
            f"({resolved_works} resolved), {len(seed['recipients'])} credited recipients "
            f"({resolved_recipients} resolved)."
        )
        return 0
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
