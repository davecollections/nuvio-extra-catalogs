"""First-party Television Academy HTML adapter; no identity or artwork guesses.

BAFTA's snapshots/lineage contracts are reused, but its source adapter cannot
parse the Academy's nomination showcases. Keep original episode/credit text
here and decide canonical work identities in the later review stage.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

ORIGIN = "https://www.televisionacademy.com"
YEAR_TEMPLATE = ORIGIN + "/awards/nominees-winners/{year}"
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class SourceError(ValueError):
    """Incomplete, ambiguous or unexpected first-party evidence."""


def clean(value: str) -> str:
    return " ".join(value.split())


def normalized(value: str) -> str:
    """Punctuation/case comparison only; never a semantic lineage decision."""
    return "".join(c for c in value.casefold() if c.isalnum())


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Node | None = field(default=None, repr=False)
    children: list[Node | str] = field(default_factory=list, repr=False)

    def has_class(self, name: str) -> bool:
        return name in self.attrs.get("class", "").split()

    def walk(self, tag: str | None = None, cls: str | None = None):
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or child.has_class(cls)):
                    yield child
                yield from child.walk(tag, cls)

    def text(self) -> str:
        if self.tag in {"script", "style", "svg"}:
            return ""
        return clean(" ".join(c.text() if isinstance(c, Node) else c for c in self.children))

    def lines(self) -> list[str]:
        def raw(node):
            if node.tag == "br":
                return "\n"
            if node.tag in {"script", "style", "svg"}:
                return ""
            return "".join(raw(c) if isinstance(c, Node) else c for c in node.children)
        return [clean(line) for line in raw(self).splitlines() if clean(line)]

    def first(self, tag: str | None = None, cls: str | None = None) -> Node | None:
        return next(self.walk(tag, cls), None)


class Document(HTMLParser):
    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict((k, v or "") for k, v in attrs), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def document(html: str, year: int) -> Node:
    root = Document(html).root
    headings = [node.text() for node in root.walk() if node.tag in {"h1", "h2"}]
    expected = re.compile(rf"^{year} - {year - 1948}(?:st|nd|rd|th) Emmy Awards$")
    if sum(bool(expected.match(heading)) for heading in headings) != 1:
        raise SourceError(f"expected exactly one {year}/{year - 1948} ceremony heading")
    return root


def annual_categories(html: str, year: int) -> list[dict]:
    root = document(html, year)
    pattern = re.compile(rf"^/awards/nominees-winners/{year}/[^/?#]+$")
    categories = {}
    for anchor in root.walk("a"):
        url = urljoin(ORIGIN, anchor.attrs.get("href", ""))
        parsed = urlparse(url)
        if parsed.netloc == "www.televisionacademy.com" and pattern.match(parsed.path):
            label = anchor.text()
            if label and url not in categories:
                categories[url] = {"url": url, "menuLabel": label, "slug": parsed.path.rsplit("/", 1)[1]}
    if not categories:
        raise SourceError(f"{year}: no category links")
    return sorted(categories.values(), key=lambda category: category["url"])


def linked_values(node: Node, prefix: str) -> list[dict]:
    values = []
    for anchor in node.walk("a"):
        url = urljoin(ORIGIN, anchor.attrs.get("href", ""))
        parsed = urlparse(url)
        if parsed.netloc == "www.televisionacademy.com" and parsed.path.startswith(prefix):
            value = {"name": anchor.text(), "url": url}
            if value["name"] and value not in values:
                values.append(value)
    return values


def structured_counts(root: Node) -> list[int]:
    counts = []
    for script in root.walk("script"):
        if script.attrs.get("type") != "application/ld+json":
            continue
        try:
            data = json.loads("".join(c for c in script.children if isinstance(c, str)))
        except json.JSONDecodeError as exc:
            raise SourceError("invalid official JSON-LD") from exc
        for value in data if isinstance(data, list) else [data]:
            if isinstance(value, dict) and value.get("@type") == "ItemList":
                items = value.get("itemListElement")
                if not isinstance(items, list):
                    raise SourceError("invalid official nomination ItemList")
                counts.append(len(items))
    return counts


def category_results(html: str, year: int, url: str) -> dict:
    root = document(html, year)
    headings = [node.text() for node in root.walk() if node.tag in {"h1", "h2"}]
    ceremony_position = next(i for i, heading in enumerate(headings) if heading.startswith(f"{year} - "))
    # Some archive titles omit Outstanding/Best. Preserve the actual heading.
    category_headings = [h for h in headings[ceremony_position + 1:] if h]
    if len(category_headings) != 1:
        raise SourceError(f"{url}: expected exactly one official category heading")
    blocks = list(root.walk(cls="showcase_placement_nominee_winners"))
    if not blocks:
        raise SourceError(f"{url}: no nomination showcases")
    nominations = []
    for block in blocks:
        states = [state for state in ("winner", "nominee") if block.has_class("nomination--" + state)]
        if len(states) != 1:
            raise SourceError(f"{url}: missing or ambiguous winner state")
        details = block.first(cls="details-container")
        if details is None:
            raise SourceError(f"{url}: missing nomination details")
        heading_node = details.first("h3") or details.first(cls="nominee-name")
        if heading_node is None:
            raise SourceError(f"{url}: missing nomination heading/credited recipient")
        heading = heading_node.text()
        if not heading:
            raise SourceError(f"{url}: empty nomination heading")
        credits = []
        blank_credits = 0
        for entry in details.walk(cls="nominee-name"):
            name = entry.text()
            if not name:
                blank_credits += 1
                continue
            role = entry.parent.first(cls="p3")
            credit = {"name": name, "role": role.text() if role else ""}
            link = entry.first("a")
            if link:
                credit["url"] = urljoin(ORIGIN, link.attrs.get("href", ""))
            credits.append(credit)
        # Performance showcases put the primary recipient in the heading.
        # Preserve the exact role/context text instead of inventing an actor role.
        linked_people = linked_values(details, "/bios/")
        primary_context = details.first(cls="text-d3")
        for person in linked_people:
            if not any(c.get("url") == person["url"] for c in credits):
                role = primary_context.text() if person["name"] == heading and primary_context else ""
                credits.append({**person, "role": role})
        programmes = linked_values(details, "/shows/")
        context = details.text()
        item = {"status": states[0], "heading": heading, "programmes": programmes,
                "credits": credits, "context": context}
        if primary_context is not None:
            item["sourceDetailLines"] = primary_context.lines()
        if blank_credits:
            item["blankCreditCount"] = blank_credits
        # Page position / Alpine display index is deliberately not an identity.
        identity = {"sourceUrl": url, **item}
        item["sourceKey"] = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        nominations.append(item)
    winners = [n for n in nominations if n["status"] == "winner"]
    if len({n["sourceKey"] for n in winners}) != len(winners):
        raise SourceError(f"{url}: duplicate full winner showcases require independent reconciliation")
    duplicate_nominees = len(nominations) - len({n["sourceKey"] for n in nominations})
    counts = structured_counts(root)
    grid = list(root.walk(cls="awards_category__nomination_grid_item"))
    grid_winners = sum(card.has_class("nomination-status--winner") for card in grid)
    if grid and len(grid) != len(nominations):
        raise SourceError(f"{url}: full showcases and nomination grid disagree: {len(nominations)} / {len(grid)}")
    if len(nominations) not in counts and len(grid) != len(nominations):
        raise SourceError(f"{url}: showcase count disagrees with official JSON-LD: {len(nominations)} / {counts}")
    if not winners:
        error = SourceError(f"{url}: no explicit winners; requires independent no-award evidence")
        error.details = {"sourceCategory": category_headings[0], "nominationCount": len(nominations),
            "structuredListCounts": counts, "nominationGridCount": len(grid),
            "winnerGridCount": grid_winners, "nominations": nominations}
        raise error
    if grid and grid_winners != len(winners):
        raise SourceError(f"{url}: full showcases and nomination grid winner counts disagree")
    diagnostics = []
    if len(nominations) not in counts:
        diagnostics.append("JSON-LD omits nomination blocks present in both full showcases and the nomination grid")
    if duplicate_nominees:
        diagnostics.append(f"{duplicate_nominees} non-winning nomination blocks repeat identical facts; original nomination count retained")
    return {"year": year, "ceremonyNumber": year - 1948, "sourceUrl": url,
            "sourceCategory": category_headings[0], "nominationCount": len(nominations),
            "structuredListCounts": counts, "nominationGridCount": len(grid),
            "winnerGridCount": grid_winners, "winnerCount": len(winners), "winners": winners,
            "sourceDiagnostics": diagnostics}
