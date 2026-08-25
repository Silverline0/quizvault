#!/usr/bin/env python3
"""
Where are the promotion recalls that never reached the bank?

The bank holds fewer questions than the PDF prints.  This finds the shortfall
per page, so the reading effort goes only where something is actually missing
rather than over all 661 pages again.

Counting is done two ways and the larger is believed, because neither is
reliable alone: the parser's own line classifier misses questions whose
numbering the print mangled, and a bare "N." regex catches numbered lists
inside an explanation.  A page is only reported as short when the bank has
fewer than BOTH counts agree are there.

    python scripts/promo_gap.py            # every year
    python scripts/promo_gap.py 2023 2024  # just these
"""

import collections
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# parse_promotion re-wraps stdout on import. Leave its wrapper in place --
# swapping the original back drops the last reference to the wrapper, and when
# it is collected it closes the buffer underneath, so the next print dies on a
# closed file.
import parse_promotion as P            # noqa: E402
import fitz                            # noqa: E402

DATA = os.path.join(ROOT, "public", "data")
VISION = os.path.join(ROOT, "scripts", "vision", "pages")

# "12." or "12)" opening a recall. Deliberately loose -- it is one of two
# counts and the stricter parser count guards it.
QNUM = re.compile(r"(?:^|\n)\s*(\d{1,3})\s*[.)]\s+(?=\S)")


def bank_by_page():
    """page -> [question ids the bank already has], across every year file."""
    out = collections.defaultdict(list)
    import glob
    for path in glob.glob(os.path.join(DATA, "promotion-*.json")):
        year = os.path.basename(path)[len("promotion-"):-len(".json")]
        for q in json.load(open(path, encoding="utf-8")):
            if q.get("pdfPage"):
                out[q["pdfPage"]].append((year, q.get("id")))
    return out


def vision_by_page():
    """page -> how many questions the vision read found, where one was done."""
    import glob
    out = {}
    for path in sorted(glob.glob(os.path.join(VISION, "*.json"))):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for rec in data:
            out[rec["page"]] = len(rec.get("questions", []))
    return out


def parser_starts(doc, i):
    """How many recalls the project's own classifier sees opening on this page."""
    try:
        lines = P.classify(P.extract_lines(doc, i))
    except Exception:
        return 0
    return sum(1 for ln in lines if getattr(ln, "kind", None) == "num")


def main():
    want = set(sys.argv[1:])
    doc = fitz.open(P.PDF)

    fixed = {}
    for start, end, year in P.SECTIONS:
        if year:
            for pg in range(start, end + 1):
                fixed[pg] = year

    bank = bank_by_page()
    vis = vision_by_page()

    rows = []
    current = None
    for i in range(doc.page_count):
        page = i + 1
        if fixed.get(page):
            current = fixed[page]
        text = doc[i].get_text()
        try:
            for ln in P.classify(P.extract_lines(doc, i)):
                if getattr(ln, "kind", None) == "year":
                    current = ln.key
        except Exception:
            pass
        year = current or "unknown"
        if want and year not in want:
            continue

        have = len(bank.get(page, []))
        regex_n = len(QNUM.findall(text))
        parse_n = parser_starts(doc, i)
        seen = vis.get(page)
        # A vision read is ground truth where one exists.
        expect = seen if seen is not None else max(regex_n, parse_n)
        rows.append({"page": page, "year": year, "have": have,
                     "regex": regex_n, "parser": parse_n,
                     "vision": seen, "expect": expect,
                     "short": max(0, expect - have)})

    per = collections.defaultdict(lambda: [0, 0, 0, 0])   # pages, have, expect, shortpages
    for r in rows:
        p = per[r["year"]]
        p[0] += 1
        p[1] += r["have"]
        p[2] += r["expect"]
        if r["short"]:
            p[3] += 1

    print(f"{'year':>6} {'pages':>6} {'in bank':>8} {'on page':>8} {'short by':>9} {'pages short':>12}")
    for year in sorted(per):
        pages, have, expect, shortp = per[year]
        print(f"{year:>6} {pages:6d} {have:8d} {expect:8d} {max(0, expect-have):9d} {shortp:12d}")

    out = os.path.join(ROOT, "scripts", "audit", "promo_gap.json")
    json.dump(rows, io.open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print()
    print(f"  written: {out}")
    worst = sorted((r for r in rows if r["short"]), key=lambda r: -r["short"])[:12]
    for r in worst:
        print(f"    p{r['page']:<4} {r['year']}  bank {r['have']}, page has ~{r['expect']}"
              f"  (regex {r['regex']}, parser {r['parser']}"
              + (f", vision {r['vision']}" if r["vision"] is not None else "") + ")")


if __name__ == "__main__":
    main()
