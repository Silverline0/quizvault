#!/usr/bin/env python3
"""
Is the figure binding right?

The recovered addresses were attributed to questions by their printed number,
and that number turns out not to be trustworthy: the PDFs carry more than one
numbered sequence, so "26." occurs several times and means something different
each time.  This binds the same addresses by the question's own STEM instead --
find the block of the PDF whose text contains this bank question's words, take
the address inside that block -- and reports how often the two agree.

Stem binding cannot drift, because it is matching content rather than a label.
Where the two disagree, the number-bound answer is the wrong one.
"""

import collections
import io
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import recover_bcsc_figures as R          # noqa: E402  (reuses its readers)

import fitz                               # noqa: E402

ROOT = R.ROOT
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def flat(text):
    return re.sub(r"\W+", " ", unicodedata.normalize("NFKC", text or "")).lower().strip()


def blocks(doc):
    """
    The document cut into question blocks, in order.

    Each block is everything from one "N." marker to the next, so a block holds
    one question's stem, its options and -- if it had one -- its figure address.
    """
    parts, marks, pos = [], [], 0
    for i in range(doc.page_count):
        text = doc[i].get_text()
        parts.append(text)
        marks.append((pos, i + 1))
        pos += len(text)
    text = "".join(parts)

    cuts = [(m.start(), int(m.group(1))) for m in R.QNUM_RE.finditer(text)]
    out = []
    for idx, (start, num) in enumerate(cuts):
        end = cuts[idx + 1][0] if idx + 1 < len(cuts) else len(text)
        page = 1
        for mark, p in marks:
            if mark <= start:
                page = p
            else:
                break
        body = text[start:end]
        urls = [u for u in (R.clean_url(mo.group(0))
                            for mo in R.URL_RE.finditer(body))
                if R.GOOD_URL.match(u)]
        out.append({"num": num, "flat": flat(body), "page": page,
                    "urls": urls, "order": idx})
    return out


def locate(stem, options, blks):
    """
    Every block whose text carries this stem.

    A question is printed twice -- once in the question list, once again above
    its explanation -- and only one of the two copies carries the figure. So
    all matching blocks are returned and their addresses pooled; taking just
    one copy would report a figure as missing half the time.
    """
    needle = flat(stem)
    for size in (70, 55, 40, 30):
        probe = needle[:size]
        if len(probe) < 20:
            continue
        hits = [b for b in blks if probe in b["flat"]]
        if len(hits) == 1:
            return hits
        if len(hits) > 1:
            # A stem like "What is the most likely diagnosis?" is shared by
            # dozens of questions, so the stem alone cannot identify one. The
            # options can: narrow to blocks that also carry this question's
            # own first two choices.
            texts = list(options.values()) if isinstance(options, dict) else list(options)
            keys = [flat(o)[:34] for o in texts[:2] if len(flat(o)) >= 12]
            if keys:
                tight = [b for b in hits
                         if all(k in b["flat"] for k in keys)]
                if tight:
                    return tight
            return hits
    return []


def main():
    mapping = R.pdf_map()
    agree = differ = onlynum = onlystem = neither = 0
    notfound = blockdry = 0
    wrong = []
    dry = []
    for bank in sorted(b for b in mapping if b.endswith("-bcsc")):
        doc = fitz.open(os.path.join(ROOT, mapping[bank]))
        blks = blocks(doc)
        numbound = R.bind(doc)
        data = json.load(open(os.path.join(R.DATA, f"{bank}.json"), encoding="utf-8"))
        b_agree = b_differ = b_only_stem = 0
        for q in data:
            if not q.get("figureRecovered"):
                continue
            n_url = (numbound.get(q["id"]) or [(None, None)])[0][0]
            hits = locate(q["question"], q.get("options") or [], blks)
            pool = [u for h in hits for u in h["urls"]]
            s_url = pool[0] if pool else None
            if not hits:
                notfound += 1
                continue
            if not pool:
                blockdry += 1
                if len(dry) < 6:
                    dry.append((bank, q["id"], [h["num"] for h in hits][:3],
                                q["question"][:60]))
                continue
            if n_url and s_url and n_url == s_url:
                agree += 1; b_agree += 1
            elif n_url and s_url:
                differ += 1; b_differ += 1
                if len(wrong) < 8:
                    wrong.append((bank, q["id"], [h["num"] for h in hits][:3],
                                  n_url[-24:], s_url[-24:], q["question"][:55]))
            elif n_url and not s_url:
                onlynum += 1
            elif s_url and not n_url:
                onlystem += 1; b_only_stem += 1
            else:
                neither += 1
        print(f"{bank:22s} agree {b_agree:4d}   disagree {b_differ:4d}   "
              f"stem found one the number missed {b_only_stem:3d}")
        doc.close()

    print(f"\n  {agree} agree, {differ} disagree, {onlynum} number-only, "
          f"{onlystem} stem-only, {neither} neither")
    print(f"  {blockdry} the stem's own block carries no address at all")
    print(f"  {notfound} the stem could not be found in the PDF")
    for d in dry:
        print(f"    dry: {d[0]} id {d[1]} (blocks {d[2]}) {d[3]!r}")
    for w in wrong:
        print(f"    {w[0]} id {w[1]}: number gave ...{w[3]}, stem (blocks {w[2]}) "
              f"gave ...{w[4]}  {w[5]!r}")


if __name__ == "__main__":
    main()
