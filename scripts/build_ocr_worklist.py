#!/usr/bin/env python3
"""
Build the OCR work list for screenshot-only recalls.

Some recalls in the source exist only as a pasted screenshot: the stem, the
choices and often the answer live inside the image and leave nothing in the text
layer, so the parser cannot reach them.  This writes one JSON task per image,
batched, for transcription.

Usage:  python scripts/build_ocr_worklist.py [--batches N]
"""

import argparse
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "public", "data")
REPORT_DIR = os.environ.get("PROMO_REPORT", os.path.join(ROOT, "scripts"))
OUT_DIR = os.environ.get("OCR_DIR", os.path.join(REPORT_DIR, "ocr"))

# Section page ranges -> exam year, mirroring parse_promotion.SECTIONS.  The
# 2018-2022 and 2016-2017 blocks interleave years, so those are resolved from
# the nearest preceding year header instead of the page range.
SECTIONS = [
    (1, 40, "2025"), (41, 84, "2024"), (85, 120, "2023"),
    (121, 296, None), (297, 448, None), (449, 542, "2015"), (543, 661, "2014"),
]


def nearest_before(page, marks, default):
    """Value of the last header at or before this page."""
    best = None
    for hp, val in marks:
        if hp <= page and (best is None or hp >= best[0]):
            best = (hp, val)
    return best[1] if best else default


def year_for(page, headers):
    for start, end, fixed in SECTIONS:
        if start <= page <= end:
            if fixed:
                return fixed
            best = None
            for hp, hy in headers:
                if hp <= page and (best is None or hp >= best[0]):
                    best = (hp, hy)
            return best[1] if best else "unknown"
    return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=7)
    args = ap.parse_args()

    with open(os.path.join(REPORT_DIR, "promotion_screenshot_only.json"),
              encoding="utf-8") as fh:
        shots = json.load(fh)

    # Year headers, so each screenshot can be filed under the right sitting.
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import fitz
    import parse_promotion as P
    doc = fitz.open(P.PDF)
    headers, subs = [], []
    for i in range(doc.page_count):
        for ln in P.classify(P.extract_lines(doc, i)):
            if ln.kind == "year":
                headers.append((ln.page, ln.key))
            elif ln.kind == "subspec":
                subs.append((ln.page, ln.key))

    tasks = []
    for shot in shots:
        for idx, url in enumerate(shot["images"]):
            path = os.path.join(ROOT, "public", url.lstrip("/").replace("/", os.sep))
            if not os.path.exists(path):
                continue
            # Cite the page the figure actually sits on: an inline image's
            # list number can be rendered a page earlier than the picture.
            import re as _re
            m = _re.match(r"p(\d+)_", os.path.basename(path))
            page = int(m.group(1)) if m else shot["page"]
            tasks.append({
                "task_id": f"p{shot['page']:03d}_n{shot['number']}_{idx}",
                "pdfPage": page,
                "subspecialty": nearest_before(page, subs, "Miscellaneous"),
                "sourceNumber": shot["number"],
                "year": year_for(shot["page"], headers),
                "imageUrl": url,
                "imagePath": path,
                "siblingCount": len(shot["images"]),
            })

    os.makedirs(OUT_DIR, exist_ok=True)
    size = (len(tasks) + args.batches - 1) // args.batches
    for b in range(args.batches):
        chunk = tasks[b * size:(b + 1) * size]
        if not chunk:
            continue
        with open(os.path.join(OUT_DIR, f"batch_{b + 1}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(chunk, fh, ensure_ascii=False, indent=1)
        print(f"batch_{b + 1}.json: {len(chunk)} images "
              f"(pages {chunk[0]['pdfPage']}-{chunk[-1]['pdfPage']})")

    print(f"\n{len(tasks)} images across {args.batches} batches -> {OUT_DIR}")


if __name__ == "__main__":
    main()
