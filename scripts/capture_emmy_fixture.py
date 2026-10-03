#!/usr/bin/env python3
"""Save small, verbatim parser fixtures from verified first-party response bytes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from emmy_source import SourceError, category_results
from fetch_emmy_snapshot import serialized, source_html

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "emmys"


class Excerpts(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.html, self.spans, self.stack = html, [], []
        self.offsets = [0]
        self.offsets.extend(match.end() for match in re.finditer("\n", html))
        self.feed(html)
        self.close()

    def absolute_position(self):
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        selected = tag in {"h1", "h2"} or (
            tag == "script" and attrs.get("type") == "application/ld+json"
        ) or any(c in classes for c in (
            "showcase_placement_nominee_winners", "awards_category__nomination_grid_item"
        ))
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, self.absolute_position(), selected))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                _, start, selected = self.stack[i]
                if selected:
                    end = self.html.index(">", self.absolute_position()) + 1
                    self.spans.append((start, end))
                del self.stack[i:]
                return

    def excerpt(self):
        spans = sorted(self.spans)
        # A selected block inside another selected block is already preserved.
        kept = []
        for start, end in spans:
            if not kept or start >= kept[-1][1]:
                kept.append((start, end))
        return "\n".join(self.html[start:end] for start, end in kept) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.name):
        parser.error("name must use lowercase letters, numbers and hyphens")
    html, evidence = source_html(args.url, args.cache_dir, offline=True)
    original = category_results(html, args.year, args.url)
    excerpt = Excerpts(html).excerpt()
    captured = category_results(excerpt, args.year, args.url)
    if original != captured:
        raise SourceError("excerpt changes parsed official facts or independent counts")
    raw = excerpt.encode("utf-8")
    filename = args.name + ".html.gz"
    (FIXTURES / filename).write_bytes(gzip.compress(raw, mtime=0))
    manifest_path = FIXTURES / "sources.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fixtures"] = [f for f in manifest["fixtures"] if f["file"] != filename]
    manifest["fixtures"].append({"file": filename, "year": args.year, "url": args.url,
        "sourceSha256": evidence["sha256"], "excerptSha256": hashlib.sha256(raw).hexdigest(),
        "nominationCount": captured["nominationCount"], "winnerCount": captured["winnerCount"]})
    manifest_path.write_text(serialized(manifest), encoding="utf-8")
    print(f"Captured {filename}: {len(raw)} bytes; facts and independent counts unchanged")


if __name__ == "__main__":
    main()
