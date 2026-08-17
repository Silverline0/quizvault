#!/usr/bin/env python3
"""
Render source PDF pages for questions whose figure is doubtful or missing.

Figure binding is geometric and imperfect -- a sampled audit put misplacement at
roughly one image in eight -- so where a figure is uncertain the reader gets the
page it came from and can settle the question by eye in one click.  The scan
shows the recall in its original layout: which picture actually sits beside
which stem.

Pages are shared between questions, so each is rendered once and referenced by
however many questions need it.

Usage:  python scripts/render_page_scans.py [--dpi 105] [--dry-run]
"""

import argparse
import glob
import io
import json
import os
import sys

import fitz

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "Promotion Exam ( 2025-2014).pdf")
DATA = os.path.join(ROOT, "public", "data")
SCAN_DIR = os.path.join(ROOT, "public", "images", "promotion-pages")
WEB_PREFIX = "/images/promotion-pages"


def needs_scan(q):
    """A question benefits from the page scan when its figure is in question."""
    if q.get("figureConfidence") in ("medium", "low"):
        return True
    if not q.get("imageUrl") and q.get("referenceLinks"):
        # Asked for a picture the source never attached -- the page shows
        # whether one is really there.
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpi", type=int, default=105)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    banks = {}
    wanted = {}
    for path in sorted(glob.glob(os.path.join(DATA, "promotion-*.json"))):
        data = json.load(open(path, encoding="utf-8"))
        banks[path] = data
        for q in data:
            if needs_scan(q) and q.get("pdfPage"):
                page = q["pdfPage"]
                wanted.setdefault(page, 0)
                wanted[page] += 1

    print(f"{sum(wanted.values())} questions want a page scan, "
          f"across {len(wanted)} distinct pages")
    if args.dry_run:
        return

    os.makedirs(SCAN_DIR, exist_ok=True)
    doc = fitz.open(PDF)
    made = 0
    total_bytes = 0
    for page in sorted(wanted):
        name = f"page_{page:03d}.jpg"
        out = os.path.join(SCAN_DIR, name)
        if not os.path.exists(out):
            pix = doc[page - 1].get_pixmap(dpi=args.dpi)
            pix.pil_save(out, format="JPEG", quality=72, optimize=True)
            made += 1
        total_bytes += os.path.getsize(out)

    attached = 0
    for path, data in banks.items():
        touched = False
        for q in data:
            if needs_scan(q) and q.get("pdfPage"):
                q["pageScanUrl"] = f"{WEB_PREFIX}/page_{q['pdfPage']:03d}.jpg"
                attached += 1
                touched = True
            elif "pageScanUrl" in q:
                del q["pageScanUrl"]
                touched = True
        if touched:
            json.dump(data, io.open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)

    # Drop scans nothing points at any more.
    keep = {f"page_{p:03d}.jpg" for p in wanted}
    removed = 0
    for name in os.listdir(SCAN_DIR):
        if name not in keep:
            os.remove(os.path.join(SCAN_DIR, name))
            removed += 1

    print(f"  rendered {made} new scans at {args.dpi} dpi "
          f"({total_bytes / 1e6:.1f} MB total, {len(wanted)} pages)")
    print(f"  attached to {attached} questions; pruned {removed} stale scans")


if __name__ == "__main__":
    main()
