#!/usr/bin/env python3
"""Offline integrity checks and explicit completion gate for Emmy source work."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

from emmy_source import SourceError
from build_emmy_release_evidence import normalized
from fetch_emmy_snapshot import INDEX_PATH, REGISTRY_PATH, SNAPSHOT_PATH, SOURCE_DIR, candidate_pages, load, no_award_exceptions, review_for_year


PRODUCER_CONTEXT_PATHS = {
    "billmoyers.com": {"/about-us/", "/series/creativity/", "/series/healing-and-the-mind/",
                       "/series/a-walk-through-the-twentieth-century/"},
    "collegebowl.com": {"/about.asp", "/index-cb.asp"},
}


def require(condition, message):
    if not condition:
        raise SourceError(message)


def source_url(value, year=None, *, context=False):
    require(isinstance(value, str), "source URL must be text")
    parsed = urlparse(value)
    hosts = {"www.televisionacademy.com"}
    if context:
        hosts.add("interviews.televisionacademy.com")
        # The broadcaster's own production records can establish format, dates
        # and credits. Its retrospective award summaries cannot replace Academy
        # winner evidence. Limit this exception to the reviewed series archive.
        if (parsed.path.startswith("/wnet/americanmasters/")
                and not {".", ".."}.intersection(unquote(parsed.path).split("/"))):
            hosts.add("www.pbs.org")
        # Exact original producer/format-owner records establish format and
        # historical production context, not Emmy outcomes or recipient roles.
        if (parsed.path in PRODUCER_CONTEXT_PATHS.get(parsed.netloc, set())
                and not parsed.params and not parsed.query and not parsed.fragment):
            hosts.add(parsed.netloc)
    require(parsed.scheme == "https" and parsed.netloc in hosts, f"unapproved source URL: {value}")
    if year is not None:
        require(parsed.path.startswith(f"/awards/nominees-winners/{year}"), f"source URL/year mismatch: {value}")
    return parsed


def evidence(value, url, *, context=False):
    require(value.get("url") == url and value.get("status") == 200, f"invalid response provenance: {url}")
    source_url(url, context=context)
    source_url(value.get("resolvedUrl"), context=context)
    require(re.fullmatch(r"[0-9a-f]{64}", value.get("sha256", "")), f"invalid source fingerprint: {url}")
    require(isinstance(value.get("byteCount"), int) and value["byteCount"] > 0, f"invalid response size: {url}")
    date.fromisoformat(value["checkedAt"])


def validate_review(review, years, indices, acquired, category_ids, context_urls=()):
    """Require the exact acquired facts reviewed for a historical allocation."""
    require(review["disposition"] in {"pending-review", "current-lineage", "excluded"}, "unknown period disposition")
    require(review.get("reason") and review.get("evidence"), "review period lacks reason/evidence")
    require(all(u in indices and indices[u][0] in years for u in review["evidence"]), "period evidence outside reviewed years")
    require(set(review.get("externalEvidence", [])) <= set(context_urls), "review period references unpinned context evidence")
    if review["disposition"] != "current-lineage":
        require("currentCategory" not in review and "winnerAllocations" not in review, "unaccepted period has category targets")
        if "reviewedSourcePages" not in review:
            return
    mixed = "winnerAllocations" in review
    require(not (mixed and "currentCategory" in review), "mixed review also carries a blanket target")
    if not mixed and review["disposition"] == "current-lineage":
        require(review.get("currentCategory") in category_ids, "lineage target outside approved scope")
    expected = {u: p for u, p in acquired.items() if u in years.values()}
    reviewed = review.get("reviewedSourcePages", [])
    require(len(reviewed) == len(expected) and {p["sourceUrl"] for p in reviewed} == set(expected), "accepted lineage does not pin every acquired page in its period")
    require(set(review.get("reviewedSourceHeadings", [])) == {p["sourceCategory"] for p in expected.values()}, "accepted historical heading review drift")
    for value in reviewed:
        page = expected[value["sourceUrl"]]
        require(value["year"] == page["year"] and value["sha256"] == page["source"]["sha256"], "accepted lineage source fingerprint drift")
        require(value["winnerSourceKeys"] == [w["sourceKey"] for w in page["winners"]], "accepted lineage winning facts drift")
    if mixed:
        expected_winners = {w["sourceKey"]: p for p in expected.values() for w in p["winners"]}
        allocations = review["winnerAllocations"]
        require(len(allocations) == len(expected_winners) and {a["sourceKey"] for a in allocations} == set(expected_winners),
                "mixed historical review does not allocate every winner exactly once")
        for value in allocations:
            page = expected_winners[value["sourceKey"]]
            require(value["sourceUrl"] == page["sourceUrl"] and value["year"] == page["year"] and value.get("reason"),
                    "winner allocation lacks its actual ceremony/page evidence")
            require(value["disposition"] in {"current-lineage", "excluded"}, "accepted mixed review conceals an unresolved winner")
            if value["disposition"] == "current-lineage":
                require(value.get("currentCategory") in category_ids, "winner allocation target outside approved scope")
            else:
                require("currentCategory" not in value, "excluded winner carries a category target")


def validate(complete=False):
    registry, index, snapshot = load(REGISTRY_PATH), load(INDEX_PATH), load(SNAPSHOT_PATH)
    require(registry.get("awardBodyId") == "emmy-awards", "incorrect canonical family")
    require(registry.get("officialCurrentCategoryCount") == 121, "current inventory requires explicit review")
    included = registry["included"]
    require((len(included), len(registry["deferred"]), len(registry["excluded"])) == (49, 69, 3), "approved 49/69/3 scope changed")
    require(len({c["id"] for c in included}) == 49, "duplicate selected IDs")
    all_names = [c["name"] for key in ("included", "deferred", "excluded") for c in registry[key]]
    require(len(set(all_names)) == 121, "duplicate inventory labels")
    for category in included:
        require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", category["id"]), "invalid selected category ID")
        source_url(category["currentPage"], 2026)
    indices = {}
    year_numbers = []
    for entry in index["years"]:
        year = entry["year"]
        require(1949 <= year <= 2026 and entry["ceremonyNumber"] == year - 1948, "invalid ceremony index")
        year_numbers.append(year)
        url = f"https://www.televisionacademy.com/awards/nominees-winners/{year}"
        evidence(entry["source"], url)
        require(entry["categoryCount"] == len(entry["categories"]) > 0, "annual category count drift")
        for category in entry["categories"]:
            parsed = source_url(category["url"], year)
            require(parsed.path.rsplit("/", 1)[1] == category["slug"], "index slug does not match discovered link")
            require(category["menuLabel"].strip(), "empty category link label")
            require(category["url"] not in indices, "duplicate annual category URL")
            indices[category["url"]] = (year, category["slug"])
    require(year_numbers == sorted(set(year_numbers), reverse=True), "duplicate/unsorted annual indices")
    require(sorted(index["requestedYears"], reverse=True) == index["requestedYears"], "unsorted requested indices")
    require(index["complete"] == (not index["failures"]), "index completeness conceals failures")
    if index["complete"]:
        require(year_numbers == index["requestedYears"], "missing acquired annual index")
    current_urls = {url for url, (year, _) in indices.items() if year == 2026}
    require({c["currentPage"] for c in included} <= current_urls, "selected current category missing from official index")
    releases = load(SOURCE_DIR / "winner-release-evidence-2026.json")
    require(releases["releaseHeadingCount"] == 120 and releases["selectedCategoryCount"] == 49, "current winner release accounting drift")
    require(len(releases["categories"]) == 49 and {c["id"] for c in releases["categories"]} == {c["id"] for c in included}, "release evidence scope differs from approved selection")
    current_categories = {c["id"]: c for c in included}
    release_files = {}
    for source in releases["sources"]:
        evidence(source, source["url"])
        require(source["pageCount"] > 0 and source["categoryHeadingCount"] > 0, "empty winner release evidence")
        require(source["file"] not in release_files, "duplicate winner release")
        release_files[source["file"]] = source
    require(len(release_files) == 3 and sum(s["categoryHeadingCount"] for s in release_files.values()) == 120, "winner release category totals drift")
    for category in releases["categories"]:
        require(category["sourceUrl"] == current_categories[category["id"]]["currentPage"], "release category/HTML URL mismatch")
        require(category["releaseFile"] in release_files, "unreferenced winner release")
        source_url(category["sourceUrl"], 2026)
        context = category["releaseContext"]
        require(hashlib.sha256(context.encode("utf-8")).hexdigest() == category["sectionSha256"], "winner release section/hash drift")
        require(re.fullmatch(r"[0-9a-f]{64}", category["htmlSourceSha256"]), "invalid cross-checked HTML fingerprint")
        require(all(normalized(n) in normalized(context) for n in category["htmlRecipientNames"] + category["htmlProgrammeNames"]), "HTML facts absent from their official winner release")
    lineage = load(SOURCE_DIR / "lineage-decisions.json")
    context_urls = set()
    for source in lineage.get("contextSources", []):
        evidence(source, source["url"], context=True)
        require(hashlib.sha256(source["context"].encode("utf-8")).hexdigest() == source["contextSha256"], "historical context/hash drift")
        require(source["url"] not in context_urls, "duplicate historical context source")
        context_urls.add(source["url"])
    decisions = [d for p in lineage["programmes"] for d in p["decisions"]]
    require(len({d["sourceSlug"] for d in decisions}) == len(decisions), "duplicate lineage review keys")
    all_slugs = {slug for _, slug in indices.values()}
    require({d["sourceSlug"] for d in decisions} == all_slugs, "historical category inventory does not account for every discovered page slug")
    require(sum(p["expectedHistoricalLabelCount"] for p in lineage["programmes"]) == len(all_slugs), "historical label count drift")
    context_by_url = {s["url"]: s for s in lineage.get("contextSources", [])}
    exception_keys = set()
    for exception in lineage.get("annualExceptions", []):
        year, slug = exception["year"], exception["sourceSlug"]
        require(1949 <= year <= 2026 and exception["ceremonyNumber"] == year - 1948, "invalid historical exception ceremony")
        require(slug in all_slugs and exception["sourceCategory"] and exception["reason"], "historical exception lacks category evidence")
        require(exception["outcome"] == "no-award", "unsupported historical exception outcome")
        require((year, slug) not in exception_keys, "duplicate historical exception")
        exception_keys.add((year, slug))
        require(exception["sourceUrl"] in context_by_url, "historical no-award lacks pinned independent evidence")
        context = context_by_url[exception["sourceUrl"]]["context"]
        require(exception["proof"] in context and re.search(r"no emmys?(?: are| is)? (?:awarded|given)", exception["proof"], re.I) and str(year) in exception["proof"],
                "historical no-award evidence does not explicitly state outcome/year")
        require(normalized(exception["sourceCategory"]) in normalized(exception["proof"]), "historical no-award evidence does not name its category")
        require(not any(p["year"] == year and p["sourceUrl"].endswith('/' + slug) for p in snapshot["pages"]), "no-award exception conflicts with a source winner page")
    validated_exceptions = no_award_exceptions(lineage)
    acquired_pages = {p["sourceUrl"]: p for p in snapshot["pages"]}
    category_ids = {c["id"] for c in included}
    for decision in decisions:
        require(decision["disposition"] in {"pending-review", "current-lineage", "excluded"}, "unknown lineage disposition")
        require(decision.get("evidence") and decision.get("reason"), "historical scope decision lacks evidence/reason")
        require(all(u in indices and indices[u][1] == decision["sourceSlug"] for u in decision["evidence"]), "historical evidence link outside discovered category")
        require(set(decision.get("externalEvidence", [])) <= context_urls, "historical decision references unpinned context evidence")
        available_urls = {year: url for url, (year, slug) in indices.items() if slug == decision["sourceSlug"]}
        available = set(available_urls)
        require(decision["firstYear"] == min(available) and decision["lastYear"] == max(available), "historical source bounds drift")
        if "acquisitionYears" in decision:
            acquired_years, excluded = set(decision["acquisitionYears"]), set(decision["excludedYears"])
            require(not acquired_years & excluded and acquired_years | excluded == available, "year-specific acquisition scope does not account for every available year")
            if decision["disposition"] == "excluded":
                require("reviewedSourcePages" in decision, "retained excluded scope lacks reviewed source facts")
        scoped_urls = {year: url for year, url in available_urls.items() if "acquisitionYears" not in decision or year in decision["acquisitionYears"]}
        if "periods" in decision:
            period_years = [year for period in decision["periods"] for year in period["years"]]
            require(len(period_years) == len(set(period_years)) and set(period_years) == set(scoped_urls), "historical review periods overlap or leave years unaccounted")
            require((decision["disposition"] == "pending-review") == any(p["disposition"] == "pending-review" for p in decision["periods"]), "top-level disposition conceals pending periods")
            require("currentCategory" not in decision, "period-specific review also carries a blanket target")
            for period in decision["periods"]:
                require(period["years"] == sorted(period["years"], reverse=True), "period years must be unique and newest first")
                urls = {year: scoped_urls[year] for year in period["years"]}
                require({u.rsplit('/', 1)[1] for u in period["evidence"]} == {decision["sourceSlug"]}, "review period references a different category slug")
                validate_review(period, urls, indices, acquired_pages, category_ids, context_urls)
            for year in scoped_urls:
                review_for_year(decision, year)
        elif decision["disposition"] == "current-lineage" or "reviewedSourcePages" in decision:
            validate_review(decision, scoped_urls, indices, acquired_pages, category_ids, context_urls)
    seen, winners, keys = set(), 0, set()
    for page in snapshot["pages"]:
        url, year = page["sourceUrl"], page["year"]
        require(url in indices and indices[url][0] == year, "snapshot page was not discovered in its annual index")
        require(url not in seen, "duplicate snapshot page")
        seen.add(url)
        evidence(page["source"], url)
        require(page["ceremonyNumber"] == year - 1948, "invalid snapshot ceremony")
        require(page["sourceCategory"].strip(), "empty official category heading")
        require(page["nominationCount"] in page["structuredListCounts"] or page.get("nominationGridCount") == page["nominationCount"], "independent count check missing")
        if page.get("nominationGridCount"):
            require(page["nominationGridCount"] == page["nominationCount"] and page["winnerGridCount"] == page["winnerCount"], "grid/showcase count mismatch")
        require(page["winnerCount"] == len(page["winners"]) > 0, "winner count mismatch")
        require(page["nominationCount"] >= page["winnerCount"], "more winners than nominations")
        winners += page["winnerCount"]
        for winner in page["winners"]:
            require(winner["status"] == "winner" and winner["heading"] and winner["context"], "invalid winner evidence")
            require(winner["sourceKey"] not in keys, "duplicate source winner identity")
            keys.add(winner["sourceKey"])
            identity = {"sourceUrl": url, **{k: v for k, v in winner.items() if k != "sourceKey"}}
            digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            require(digest == winner["sourceKey"], "winner facts/source key drift")
            require("mediaType" not in winner and "tmdbId" not in winner, "source snapshot contains unreviewed enrichment")
            for programme in winner["programmes"]:
                source_url(programme["url"])
                require(programme["name"].strip(), "empty programme name")
            for credit in winner["credits"]:
                require(credit["name"].strip() and isinstance(credit["role"], str), "invalid recipient credit")
                if credit.get("url"):
                    source_url(credit["url"])
    require(snapshot["pageCount"] == len(seen) and snapshot["winnerRecordCount"] == winners, "snapshot totals drift")
    for page in snapshot.get("noAwardPages", []):
        url, year = page["sourceUrl"], page["year"]
        require(url in indices and indices[url][0] == year and url not in seen, "unindexed or duplicate no-award page")
        seen.add(url)
        evidence(page["source"], url)
        require(page["outcome"] == "no-award" and page["winnerCount"] == page["winnerGridCount"] == 0 and not page["winners"], "no-award page conceals winners")
        require(page["independentNoAward"] == validated_exceptions.get(url), "no-award page lacks the independently validated exception")
        require(page["nominationCount"] == len(page["nominationEvidence"]) and not any(n["status"] == "winner" for n in page["nominationEvidence"]), "no-award nomination evidence/count drift")
        require(page["nominationCount"] in page["structuredListCounts"] or page["nominationGridCount"] == page["nominationCount"], "no-award page lacks independent nomination accounting")
    current_pages = {p["sourceUrl"]: p for p in snapshot["pages"] if p["year"] == 2026}
    for category in releases["categories"]:
        page = current_pages.get(category["sourceUrl"])
        if page is None:
            continue
        require(page["source"]["sha256"] == category["htmlSourceSha256"], "release evidence references different current HTML bytes")
        names = list(dict.fromkeys(c["name"] for w in page["winners"] for c in w["credits"]))
        programmes = list(dict.fromkeys(p["name"] for w in page["winners"] for p in w["programmes"]))
        require(names == category["htmlRecipientNames"] and programmes == category["htmlProgrammeNames"], "release evidence and current source winner facts disagree")
    require(snapshot["completeAcquisition"] == (not snapshot["failures"]), "snapshot completeness conceals errors")
    requested = {e["url"] for e in candidate_pages(index["years"], lineage) if e["year"] in snapshot["requestedYears"]}
    failed_urls = {e["input"]["url"] for e in snapshot["failures"]}
    for failure in snapshot["failures"]:
        source_url(failure["input"]["url"], failure["input"]["year"])
        require(failure["kind"] in {"source-conflict", "extraction-error", "http-error", "external-service-error"}, "unclassified source failure")
        date.fromisoformat(failure["checkedAt"])
        if "source" in failure:
            evidence(failure["source"], failure["input"]["url"])
        if "rejectedPageEvidence" in failure:
            rejected = failure["rejectedPageEvidence"]
            require(rejected["nominationCount"] == len(rejected["nominations"]), "rejected nomination accounting drift")
            require(not any(n["status"] == "winner" for n in rejected["nominations"]), "no-winner failure conceals a marked winner")
        if failure["kind"] == "source-conflict":
            conflict = failure["conflictingWinnerEvidence"]
            url = failure["input"]["url"]
            require(conflict["independentNoAward"] == validated_exceptions.get(url), "source conflict lacks independently pinned evidence")
            html = conflict["html"]
            require(html["sourceUrl"] == url and html["year"] == failure["input"]["year"] and html["winnerCount"] == len(html["winners"]) > 0, "source conflict omits the actual conflicting HTML winners")
            require(html["nominationCount"] in html["structuredListCounts"] or html["nominationGridCount"] == html["nominationCount"], "conflicting source lacks independent nomination accounting")
            require(normalized(html["sourceCategory"]) == normalized(conflict["independentNoAward"]["sourceCategory"]), "conflicting sources name different categories")
            for winner in html["winners"]:
                identity = {"sourceUrl": url, **{k: v for k, v in winner.items() if k != "sourceKey"}}
                require(winner["status"] == "winner" and hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest() == winner["sourceKey"], "conflicting winner facts/source key drift")
    require(not seen & failed_urls and seen | failed_urls == requested, "candidate pages missing from success/failure accounting")
    pending = any(d["disposition"] == "pending-review" for d in decisions)
    if pending or not snapshot["completeAcquisition"]:
        root = SOURCE_DIR.parents[2]
        manifests = [root / "manifest.json", *root.glob("presets/**/manifest.json")]
        for path in manifests:
            manifest = load(path)
            require(manifest.get("id") != "com.davecollections.nuvio.extra.emmys" and
                    not any(c["id"].startswith("emmy-") for c in manifest["catalogs"]),
                    "Emmy catalogues/presets cannot publish before source acquisition and lineage review are complete")
        require(not list(root.glob("catalog/*/emmy-*.json")) and not list(root.glob("presets/**/catalog/*/emmy-*.json")),
                "Unlisted static Emmy routes cannot bypass the historical review gate")
    if complete:
        require(year_numbers == list(range(2026, 1948, -1)), "all 78 annual indices required")
        require(snapshot["requestedYears"] == year_numbers and snapshot["completeAcquisition"], "historical acquisition is incomplete")
        require(not any(d["disposition"] == "pending-review" for d in decisions), "historical lineage review is incomplete")
    return len(year_numbers), len(indices), len(snapshot["pages"]), winners, sum(d["disposition"] == "pending-review" for d in decisions)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--complete", action="store_true", help="require finished acquisition and historical lineage review")
    args = parser.parse_args()
    try:
        years, links, pages, winners, pending = validate(args.complete)
        print(f"Emmy evidence valid: {years} annual indices, {links} category links, {pages} acquired pages, {winners} winners; {pending} lineage reviews pending")
        return 0
    except (SourceError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
