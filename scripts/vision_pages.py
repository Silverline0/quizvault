#!/usr/bin/env python3
"""
Page manifest and renderer for the vision rebuild of the Promotion banks.

`parse_promotion.py` reads the PDF's text layer and anchors on runs of lettered
options.  That works for the 2023-2025 sections, which are typed out, and fails
on the older ones, where a recall is often a pasted SCREENSHOT: the stem and all
its choices live inside an image, and only "Answer: D" and an explanation are
text.  No text options means no anchor, so the parser emits nothing and the
orphaned answer text drifts onto a neighbouring question.

That is why 2020 has 25 pages and zero published questions.

This module does not try to fix the parser.  It supports reading the pages
directly:

    python scripts/vision_pages.py plan            # page -> year, with status
    python scripts/vision_pages.py render 131 140  # write PNGs for a range
    python scripts/vision_pages.py todo 2020       # pages still unread

Extractions are appended to scripts/vision/pages.jsonl, one record per page.
Nothing here writes to public/data -- see merge_vision.py for that.
"""

import argparse
import collections
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

VISION_DIR = os.path.join(ROOT, "scripts", "vision")
PAGES_JSONL = os.path.join(VISION_DIR, "pages.jsonl")
# Rendered pages are large and reproducible, so they live outside the repo.
CACHE = os.environ.get(
    "VISION_CACHE",
    os.path.join(os.environ.get("TEMP", "/tmp"), "quizvault-pages"),
)
ZOOM = 1.7  # ~1040x1470 -- readable without being wasteful


def year_by_page():
    """The exam year in force on each page, decided exactly as the parser does."""
    import fitz
    import parse_promotion as P

    doc = fitz.open(P.PDF)
    fixed = {}
    for start, end, year in P.SECTIONS:
        for pg in range(start, end + 1):
            fixed[pg] = year

    out, current = {}, None
    for i in range(doc.page_count):
        page = i + 1
        if fixed.get(page):
            current = fixed[page]
        for ln in P.classify(P.extract_lines(doc, i)):
            if ln.kind == "year":
                current = ln.key
        out[page] = current or "unknown"
    return out, doc.page_count


def published_by_page():
    import glob

    counts = collections.Counter()
    for path in glob.glob(os.path.join(ROOT, "public", "data", "promotion-*.json")):
        for q in json.load(open(path, encoding="utf-8")):
            if q.get("pdfPage"):
                counts[q["pdfPage"]] += 1
    return counts


def read_done():
    """
    Pages already extracted, so a resumed run never repeats work.

    Each batch is its own JSON file under scripts/vision/pages/. Separate files
    rather than one appended log: a batch is written whole or not at all, stays
    independently reviewable, and never needs shell quoting to produce.
    """
    import glob

    done = {}
    for path in sorted(glob.glob(os.path.join(VISION_DIR, "pages", "*.json"))):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  !! {os.path.basename(path)}: {exc}", file=sys.stderr)
            continue
        for rec in data:
            done[rec["page"]] = rec
    return done


def cmd_plan(args):
    years, total = year_by_page()
    pub = published_by_page()
    done = read_done()

    per = collections.defaultdict(lambda: [0, 0, 0])  # pages, published, read
    for page in range(1, total + 1):
        y = years[page]
        per[y][0] += 1
        per[y][1] += pub.get(page, 0)
        per[y][2] += 1 if page in done else 0

    print(f"{'year':>8} {'pages':>6} {'published':>10} {'per page':>9} {'read':>6} {'left':>6}")
    for y in sorted(per, reverse=True):
        pages, published, read = per[y]
        print(f"{y:>8} {pages:6d} {published:10d} {published / pages:9.2f} "
              f"{read:6d} {pages - read:6d}")
    print(f"\n  total pages {total}   read {len(done)}   left {total - len(done)}")


def cmd_render(args):
    import fitz
    import parse_promotion as P

    os.makedirs(CACHE, exist_ok=True)
    doc = fitz.open(P.PDF)
    first, last = args.first, args.last or args.first
    written = []
    for page in range(first, last + 1):
        if page < 1 or page > doc.page_count:
            continue
        out = os.path.join(CACHE, f"p{page:03d}.png")
        if not os.path.exists(out) or args.force:
            pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
            pix.save(out)
        written.append(out)
    for path in written:
        print(path)
    print(f"\n  {len(written)} page(s) in {CACHE}", file=sys.stderr)


def cmd_crop(args):
    """
    Blow up one region of a page.

    The compiler often pastes the original exam screenshot at thumbnail size,
    so the distractors are present but unreadable at page zoom. Coordinates are
    given in the pixels of the rendered page, which is what you are reading
    from, rather than in PDF points.
    """
    import fitz
    import parse_promotion as P

    os.makedirs(CACHE, exist_ok=True)
    doc = fitz.open(P.PDF)
    scale = args.zoom / ZOOM
    clip = fitz.Rect(args.x0 / ZOOM, args.y0 / ZOOM, args.x1 / ZOOM, args.y1 / ZOOM)
    pix = doc[args.page - 1].get_pixmap(matrix=fitz.Matrix(args.zoom, args.zoom), clip=clip)
    out = os.path.join(CACHE, f"p{args.page:03d}_crop.png")
    pix.save(out)
    print(out)
    print(f"  {pix.width}x{pix.height} at {scale:.1f}x page zoom", file=sys.stderr)


def cmd_todo(args):
    years, total = year_by_page()
    done = read_done()
    pages = [p for p in range(1, total + 1)
             if (not args.year or years[p] == args.year) and p not in done]
    print(" ".join(str(p) for p in pages[: args.limit]))
    print(f"\n  {len(pages)} page(s) left"
          + (f" for {args.year}" if args.year else "")
          + f"; showing {min(args.limit, len(pages))}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("plan").set_defaults(func=cmd_plan)

    r = sub.add_parser("render")
    r.add_argument("first", type=int)
    r.add_argument("last", type=int, nargs="?")
    r.add_argument("--force", action="store_true")
    r.set_defaults(func=cmd_render)

    c = sub.add_parser("crop")
    c.add_argument("page", type=int)
    c.add_argument("x0", type=float)
    c.add_argument("y0", type=float)
    c.add_argument("x1", type=float)
    c.add_argument("y1", type=float)
    c.add_argument("--zoom", type=float, default=6.0)
    c.set_defaults(func=cmd_crop)

    t = sub.add_parser("todo")
    t.add_argument("year", nargs="?")
    t.add_argument("--limit", type=int, default=40)
    t.set_defaults(func=cmd_todo)

    args = ap.parse_args()
    os.makedirs(VISION_DIR, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
