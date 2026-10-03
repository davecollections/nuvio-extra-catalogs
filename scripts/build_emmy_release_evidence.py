#!/usr/bin/env python3
"""Cross-check 2026 HTML winners against pinned official winner releases.

PDF extraction is maintenance-only; CI validates committed evidence without
downloading sources or requiring a PDF library. Preserve complete release text
so recipients omitted by HTML remain available for individual review.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from emmy_source import SourceError, category_results
from fetch_emmy_snapshot import REGISTRY_PATH, SOURCE_DIR, serialized, load, source_html

OUTPUT_PATH = SOURCE_DIR / "winner-release-evidence-2026.json"


def normalized(value):
    return "".join(c for c in value.casefold() if c.isalnum())


def sections(text, inventory):
    lines = text.splitlines(keepends=True)
    offset, found = 0, []
    aliases = {normalized(c["name"]): c["name"] for c in inventory}
    for i, line in enumerate(lines):
        if line.strip():
            for width in range(1, 5):
                label = aliases.get(normalized(" ".join(lines[i:i + width])))
                if label:
                    found.append((offset, label))
                    break
        offset += len(line)
    if len({label for _, label in found}) != len(found):
        raise SourceError("duplicate category headings in official release")
    result = {}
    for i, (start, label) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(text)
        section = text[start:end]
        section = re.split(r"PROGRAMS? WITH MULTIPLE AWARDS", section, flags=re.IGNORECASE)[0]
        result[label] = section.strip()
    return result


def build(pdf_dir, html_cache):
    from pypdf import PdfReader

    registry = load(REGISTRY_PATH)
    inventory = [c for group in ("included", "deferred", "excluded") for c in registry[group]]
    acquisitions = load_list(pdf_dir / "acquisition.json")
    sources, release_sections = [], {}
    for entry in acquisitions:
        if not entry["file"].startswith("winners-2026-"):
            continue
        path = pdf_dir / entry["file"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"] or len(raw) != entry["bytes"]:
            raise SourceError(f"{path}: official release fingerprint mismatch")
        if entry["status"] != 200 or not entry["finalUrl"].startswith("https://www.televisionacademy.com/"):
            raise SourceError(f"{path}: unexpected release provenance")
        pages = PdfReader(path).pages
        text = "\n".join(page.extract_text() for page in pages)
        extracted = sections(text, inventory)
        for label, context in extracted.items():
            if label in release_sections:
                raise SourceError(f"category appears in multiple releases: {label}")
            release_sections[label] = (entry["file"], context)
        sources.append({"file": entry["file"], "url": entry["url"], "resolvedUrl": entry["finalUrl"],
            "status": entry["status"], "sha256": entry["sha256"], "byteCount": len(raw),
            "checkedAt": registry["checkedAt"], "pageCount": len(pages), "categoryHeadingCount": len(extracted)})
    expected_labels = {c["name"] for c in inventory if c["currentPage"] is not None}
    if set(release_sections) != expected_labels or len(expected_labels) != 120:
        raise SourceError("official release headings do not reconcile the 120 result categories")
    categories = []
    for category in registry["included"]:
        filename, context = release_sections[category["name"]]
        html, source = source_html(category["currentPage"], html_cache, offline=True)
        parsed = category_results(html, 2026, category["currentPage"])
        names = list(dict.fromkeys(c["name"] for w in parsed["winners"] for c in w["credits"]))
        work_names = list(dict.fromkeys(p["name"] for w in parsed["winners"] for p in w["programmes"]))
        missing = [name for name in names + work_names if normalized(name) not in normalized(context)]
        if missing:
            raise SourceError(f"{category['name']}: HTML facts absent from winner release: {missing}")
        # Candidates expose release-only credits. No identity or role is accepted
        # from this text pattern without the subsequent individual review.
        credit_lines = [line.strip() for line in context.splitlines() if re.search(
            r",\s*(?:.*Producer|.*Director|.*Writer|.*Written|.*Creator|.*Host|.*Narrator|.*Animation|.*Story|.*Developed)", line, re.IGNORECASE)]
        extra_names = [line.split(",", 1)[0] for line in credit_lines
                       if normalized(line.split(",", 1)[0]) not in {normalized(n) for n in names}]
        categories.append({"id": category["id"], "name": category["name"], "sourceUrl": category["currentPage"],
            "htmlSourceSha256": source["sha256"], "releaseFile": filename, "releaseContext": context,
            "sectionSha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
            "htmlRecipientNames": names, "htmlProgrammeNames": work_names,
            "releaseRecipientLineCandidates": credit_lines, "additionalRecipientNameCandidates": extra_names,
            "creditReviewStatus": "pending-review"})
    return {"schemaVersion": 1, "checkedAt": registry["checkedAt"], "authority": registry["authority"],
        "policy": "All selected HTML programme/recipient names occur in matching official release sections. Full release credits are retained; differences remain pending individual recipient review, not accepted identity mappings.",
        "releaseHeadingCount": len(release_sections), "selectedCategoryCount": len(categories),
        "sources": sources, "categories": categories}


def load_list(path):
    import json
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise SourceError(f"{path}: expected response acquisition list")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", type=Path, required=True)
    parser.add_argument("--html-cache", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not (args.write or args.check):
        parser.error("choose --write or --check")
    value = build(args.pdf_dir, args.html_cache)
    content = serialized(value)
    if args.write:
        OUTPUT_PATH.write_text(content, encoding="utf-8")
    if args.check and OUTPUT_PATH.read_text(encoding="utf-8") != content:
        raise SourceError("official release evidence is stale")
    gaps = sum(bool(c["additionalRecipientNameCandidates"]) for c in value["categories"])
    print(f"Reconciled {value['releaseHeadingCount']} release headings and all 49 selected HTML winners; {gaps} categories have additional recipient candidates to review")


if __name__ == "__main__":
    main()
