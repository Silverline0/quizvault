#!/usr/bin/env python3
"""
Attach verified reference-image links to questions with a doubtful or missing
figure.

Roughly one figure in eight is bound to the wrong question (measured), and 36
questions ask for a picture the source never included.  Rather than guess at a
replacement, each affected question carries links to an openly-licensed page
showing the finding it describes, so the reader can see the real thing.

Only links are stored, never images: nothing is copied, hotlinked or rehosted.

A link is accepted only if the researcher marked it verified (they fetched it),
it is http(s), it points at a page rather than an image file, and its host is on
the allow-list of medical reference sites.  Everything rejected is reported.

Usage:  python scripts/merge_figure_links.py [--dry-run]
"""

import argparse
import collections
import glob
import io
import json
import os
import re
import sys
from urllib.parse import urlparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "public", "data")
REPORT_DIR = os.environ.get("PROMO_REPORT", os.path.join(ROOT, "scripts"))
FIG_DIR = os.environ.get("FIGURE_DIR", os.path.join(REPORT_DIR, "figures"))

# Reputable, openly accessible ophthalmology references.
ALLOWED_HOSTS = (
    "eyewiki.org", "eyewiki.aao.org", "commons.wikimedia.org",
    "en.wikipedia.org", "nei.nih.gov", "ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
    "statpearls.com", "imagebank.asrs.org", "webeye.ophth.uiowa.edu",
    "eyerounds.org", "aao.org", "medlineplus.gov", "nih.gov",
    # University and society teaching collections, openly accessible.
    "morancore.utah.edu", "aapos.org", "vagelos.columbia.edu",
)
IMAGE_FILE_RE = re.compile(r"\.(jpe?g|png|gif|webp|bmp|tiff?)(\?|$)", re.I)
# A MediaWiki "File:" URL is a description page carrying the image, its author
# and its licence -- exactly what we want to link to -- even though it ends in
# an image extension.
WIKI_FILE_PAGE_RE = re.compile(r"/wiki/(File|Media):", re.I)
MAX_LINKS = 3


def host_ok(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def vet(link):
    """Return (ok, reason)."""
    url = (link.get("url") or "").strip()
    if not url:
        return False, "empty url"
    if not url.lower().startswith(("http://", "https://")):
        return False, "not http(s)"
    if not link.get("verified"):
        return False, "researcher did not verify it loads"
    if IMAGE_FILE_RE.search(url) and not WIKI_FILE_PAGE_RE.search(url):
        return False, "points at an image file, not a page"
    if not host_ok(url):
        return False, f"host not on the reference allow-list ({urlparse(url).hostname})"
    if not (link.get("title") or "").strip():
        return False, "no title"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    results = []
    for path in sorted(glob.glob(os.path.join(FIG_DIR, "fig_result_*.json"))):
        with open(path, encoding="utf-8") as fh:
            try:
                results.extend(json.load(fh))
            except json.JSONDecodeError as exc:
                print(f"  !! {os.path.basename(path)} is not valid JSON: {exc}")
    if not results:
        print("no researcher results found; nothing to merge")
        return

    accepted, rejected = {}, []
    for r in results:
        good = []
        for link in (r.get("links") or []):
            ok, why = vet(link)
            if ok:
                good.append({"title": link["title"].strip(),
                             "url": link["url"].strip(),
                             "source": (link.get("source") or "").strip(),
                             "shows": (link.get("shows") or "").strip()})
            else:
                rejected.append({"task_id": r.get("task_id"),
                                 "url": link.get("url"), "reason": why})
        # Drop duplicate URLs, keep order, cap the list.
        seen, deduped = set(), []
        for link in good:
            if link["url"] in seen:
                continue
            seen.add(link["url"])
            deduped.append(link)
        if deduped:
            accepted[r["task_id"]] = {"finding": (r.get("finding") or "").strip(),
                                      "links": deduped[:MAX_LINKS]}

    print(f"{len(results)} researched questions")
    print(f"  with at least one usable link: {len(accepted)}")
    print(f"  links rejected: {len(rejected)}")
    for why, n in collections.Counter(x["reason"].split("(")[0].strip()
                                      for x in rejected).most_common():
        print(f"     {n:4d}  {why}")

    hosts = collections.Counter(urlparse(l["url"]).hostname
                                for v in accepted.values() for l in v["links"])
    print("  sources:", dict(hosts.most_common()))

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "promotion_link_rejects.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rejected, fh, ensure_ascii=False, indent=1)

    if args.dry_run:
        print("\ndry run: no bank files written")
        return

    attached = 0
    for path in sorted(glob.glob(os.path.join(DATA, "promotion-*.json"))):
        data = json.load(open(path, encoding="utf-8"))
        touched = False
        for q in data:
            key = f"{q['source']}#{q['id']}"
            entry = accepted.get(key)
            if not entry:
                q.pop("referenceLinks", None)
                continue
            q["referenceLinks"] = entry["links"]
            if entry["finding"]:
                q["figureFinding"] = entry["finding"]
            attached += 1
            touched = True
        if touched:
            json.dump(data, io.open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)

    print(f"\n  reference links attached to {attached} questions")


if __name__ == "__main__":
    main()
