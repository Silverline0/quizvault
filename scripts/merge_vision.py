#!/usr/bin/env python3
"""
Turn the page-by-page vision extractions into published banks.

`parse_promotion.py` reads the PDF's text layer and anchors on runs of lettered
options.  Where a recall was pasted in as a screenshot -- stem and choices
inside an image, only "Answer: D" as text -- it has nothing to anchor on and
emits nothing.  Those pages were read directly instead; this merges the result.

Provenance is carried into every record rather than flattened away, because
these keys did not all come from the same place:

  keyFrom "text"            the compiler wrote the answer out
          "marked_in_image" only the exam screenshot shows which choice is right
          "both"            the two agree
  sourceHint                what the compiler wrote where an answer should be
                            ("?", "E", "D ???") when they were not sure
  authoredDistractors       the compiler recorded only the correct answer, so
                            the wrong options were written for this bank
  visionRead                read from the page image, not the text layer

Every vision-read question also carries a scan of its source page, since the
page is the evidence for both the stem and the key.

Usage:  python scripts/merge_vision.py [--year 2020] [--dry-run]
"""

import argparse
import collections
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

DATA = os.path.join(ROOT, "public", "data")
BATCHES = os.path.join(ROOT, "scripts", "vision", "pages")
SCAN_DIR = os.path.join(ROOT, "public", "images", "promotion-pages")
SCAN_WEB = "/images/promotion-pages"
SCAN_ZOOM = 2.0


def load_batches():
    """Every page record on disk, newest file wins if a page is repeated."""
    pages = {}
    for path in sorted(glob.glob(os.path.join(BATCHES, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            for rec in json.load(fh):
                pages[rec["page"]] = rec
    return pages


def page_context():
    """Subspecialty in force on each page, from the parser's own classifier."""
    import fitz
    import parse_promotion as P

    doc = fitz.open(P.PDF)
    subs, current = {}, None
    for i in range(doc.page_count):
        for ln in P.classify(P.extract_lines(doc, i)):
            if ln.kind == "subspec":
                current = ln.key
        subs[i + 1] = current or "Miscellaneous"
    return subs


def render_scan(page):
    """One JPEG per contributing page. The page is the evidence, so it ships."""
    import fitz
    import parse_promotion as P

    os.makedirs(SCAN_DIR, exist_ok=True)
    out = os.path.join(SCAN_DIR, f"page_{page:03d}.jpg")
    if not os.path.exists(out):
        doc = fitz.open(P.PDF)
        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(SCAN_ZOOM, SCAN_ZOOM))
        pix.save(out, jpg_quality=72)
    return f"{SCAN_WEB}/page_{page:03d}.jpg"


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def build(pages, subs):
    by_year = collections.defaultdict(list)
    for page in sorted(pages):
        rec = pages[page]
        for q in rec["questions"]:
            year = q.get("year") or rec["year"]
            item = {
                "id": 0,
                "source": f"promotion-{year}",
                "question": q["stem"],
                "options": q["options"],
                "correctAnswer": q["answer"],
                "year": year,
                "subspecialty": q.get("subspecialty") or subs.get(page, "Miscellaneous"),
                "pdfPage": page,
                "visionRead": True,
                "keyFrom": q["answerSource"],
                "pageScanUrl": render_scan(page),
            }
            if q.get("explanation"):
                item["explanation"] = q["explanation"]
            if q.get("reference"):
                item["explanation"] = (item.get("explanation", "") +
                                       f"  Reference: {q['reference']}").strip()
            if q.get("authoredDistractors"):
                item["authoredDistractors"] = True
            if q.get("sourceAnswerText") is not None:
                # An empty string is meaningful: the compiler left it blank.
                item["sourceHint"] = q["sourceAnswerText"]
            # Notes are written to add to the panel's own provenance line, not
            # to restate it, so they ship as recorded.
            if q.get("compilerNote"):
                item["sourceNote"] = q["compilerNote"]
            by_year[year].append(item)
    return by_year


def merge_into_bank(year, fresh, dry):
    """Add to an existing bank if the parser already built one, else create it."""
    path = os.path.join(DATA, f"promotion-{year}.json")
    existing = []
    if os.path.exists(path):
        existing = json.load(open(path, encoding="utf-8"))

    seen = {norm(q["question"]) for q in existing}
    added, dupes = [], 0
    for q in fresh:
        key = norm(q["question"])
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        added.append(q)

    merged = existing + added
    merged.sort(key=lambda q: (q.get("pdfPage") or 0, q["question"][:40]))
    for i, q in enumerate(merged, 1):
        q["id"] = i
        q["source"] = f"promotion-{year}"

    if not dry:
        with io.open(path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False, indent=1)
    return existing, added, dupes, merged


def register(year, count, dry):
    path = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(path, encoding="utf-8"))
    bank = f"promotion-{year}"
    sets = [s for s in manifest["questionSets"] if s["id"] != bank]
    sets.append({
        "id": bank,
        "name": f"Promotion {year}",
        "description": f"{count} recalls from the {year} promotion exam.",
        "file": f"{bank}.json",
        "questionCount": count,
        "category": "promotion",
        "source": "Promotion",
    })
    sets.sort(key=lambda s: s["id"])
    manifest["questionSets"] = sets
    if not dry:
        with io.open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", action="append", help="only merge these years")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pages = load_batches()
    subs = page_context()
    by_year = build(pages, subs)

    print(f"pages read: {len(pages)}   questions extracted: "
          f"{sum(len(v) for v in by_year.values())}")
    for year in sorted(by_year, reverse=True):
        print(f"    {year}: {len(by_year[year])}")

    targets = args.year or sorted(by_year)
    print()
    for year in sorted(targets, reverse=True):
        if year not in by_year:
            print(f"  {year}: nothing extracted yet")
            continue
        before, added, dupes, merged = merge_into_bank(year, by_year[year], args.dry_run)
        register(year, len(merged), args.dry_run)
        print(f"  promotion-{year}: {len(before)} existing + {len(added)} new "
              f"= {len(merged)}" + (f"   ({dupes} already present)" if dupes else ""))
        keyed = collections.Counter(q.get("keyFrom") for q in added)
        unsure = sum(1 for q in added if q.get("sourceHint") not in (None, ""))
        blank = sum(1 for q in added if q.get("sourceHint") == "")
        authored = sum(1 for q in added if q.get("authoredDistractors"))
        print(f"      key from: {dict(keyed)}")
        print(f"      compiler was unsure of the key: {unsure}   left it blank: {blank}")
        print(f"      distractors written for this bank: {authored}")

    if args.dry_run:
        print("\ndry run: nothing written")


if __name__ == "__main__":
    main()
