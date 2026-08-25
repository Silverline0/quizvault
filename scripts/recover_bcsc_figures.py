#!/usr/bin/env python3
"""
Recover the BCSC figures that never made it into the source PDFs.

The seven BCSC PDFs are print-outs of the AAO web question bank.  Its figures
were remote images on qas.aao.org, and when the pages were printed many of them
failed to load and were rendered as their own URL in plain text.  Around 700
such placeholders survive across the PDFs.  The pictures themselves are still
served at those URLs, so the questions are recoverable rather than lost.

Reading an address back out is the whole difficulty, because the print damaged
it in four different ways at once:

  * it wrapped mid-address, sometimes over a page break, so the id arrives in
    up to five pieces;
  * it drew Glyphicons' broken-image mark at the wrap point, which lands INSIDE
    the address as an invisible private-use character;
  * it substituted typographic ligatures inside the hex, so "9eff9dc7" prints
    as "9e<ff>9dc7";
  * and the extractor's own ordering slots unrelated page content between the
    pieces -- headings in one reading order, answer percentages in the other.

No single reading order survives all four, so the document is read three ways
and the results are unioned per question.  Every candidate is then held to the
one legal shape -- id is a UUID, t is a timestamp -- and anything that fails is
dropped rather than requested, so a mangled address can never be silently
fetched as a 404 page and attached as a figure.

    python scripts/recover_bcsc_figures.py map cornea-bcsc     # bind, write plan
    python scripts/recover_bcsc_figures.py fetch cornea-bcsc   # download + attach
"""

import argparse
import collections
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "public", "data")
AUDIT = os.path.join(ROOT, "scripts", "audit")
IMAGES = os.path.join(ROOT, "public", "images")

# The print wraps the address hard -- the id alone can be broken over five
# lines -- so the match has to run THROUGH newlines to the closing bracket.
# Stopping at the first space, as an ordinary URL pattern does, yields
# "image.axd?" and nothing else.
URL_RE = re.compile(r"https?://[^\s)]*?image\.axd[^)]{0,400}", re.I)
# The one legal shape. Everything the print mangled fails this.
GOOD_URL = re.compile(r"^https://qas\.aao\.org/full/image\.axd\?id="
                      r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                      r"&t=\d+$", re.I)
# A span that continues an address: hex, dashes, and the two parameter names.
# Prose fails it on its non-hex letters, a percentage on its "%".
CONT_RE = re.compile(r"^(id=)?[0-9a-fA-F-]*(&t=\d+)?\)?$")
# "79." at the start of a question block.
QNUM_RE = re.compile(r"(?:^|\n)\s*(\d{1,4})\.\s+(?=[A-Z(])")
# Anything outside a URL's own alphabet is print damage, not address. This is
# what removes the invisible broken-image glyph.
JUNK_RE = re.compile(r"[^A-Za-z0-9:/?=&.\-_%~+]")
# A printed question -- stem, options, explanation -- runs to a few thousand
# characters. Anything far past that is not a question but a failure to find
# the markers at all: the sort=True reading of the Uveitis PDF yielded a single
# 552,000-character "block" holding 37 addresses, and because it contained
# every stem in the document, every question matched it and inherited all 37.
MAX_BLOCK = 8000
# How far into a block its own stem may start. A block opens with its printed
# number and then the stem, so this only has to clear the number itself; it is
# generous to absorb a stray header the extractor put first.
STEM_AT = 200


def pdf_map():
    return json.load(open(os.path.join(AUDIT, "bank_pdfs.json"), encoding="utf-8"))


def clean_url(raw):
    """Ligatures back to letters, decoration out, wrap closed up."""
    return JUNK_RE.sub("", unicodedata.normalize("NFKC", raw)).rstrip(")")


def flat_pass(doc, sort):
    """
    The document as one string, each address attributed to the question whose
    text encloses it.

    Page proximity would not do: on page 89 of the Cornea PDF the placeholder
    belongs to question 78 while question 79's stem starts lower down, and 79's
    own figure sits on page 90.

    Both block orderings are read, because they fail on different questions:
    the default slots a page's headings between the halves of an address that
    wrapped over a page break, while sort=True slots in the answer percentages
    that sit at the same height further across the page.
    """
    parts, marks, pos = [], [], 0
    for i in range(doc.page_count):
        text = doc[i].get_text(sort=sort)
        parts.append(text)
        marks.append((pos, i + 1))
        pos += len(text)
    text = "".join(parts)

    cuts = [(m.start(), int(m.group(1))) for m in QNUM_RE.finditer(text)]
    out = collections.defaultdict(list)
    for idx, (start, qnum) in enumerate(cuts):
        end = cuts[idx + 1][0] if idx + 1 < len(cuts) else len(text)
        for mo in URL_RE.finditer(text, start, end):
            url = clean_url(mo.group(0))
            if not GOOD_URL.match(url):
                continue
            page = 1
            for mark, p in marks:
                if mark <= mo.start():
                    page = p
                else:
                    break
            out[qnum].append((url, page))
    return out


def span_pass(doc):
    """
    Rebuild each address from its own spans instead of from flat text.

    A span is one run of same-styled text, so the address survives as a handful
    of them; walking forward and accepting only spans that could continue an
    address steps over the interleaved content that defeats both flat readings.
    """
    rows = []
    for i in range(doc.page_count):
        page = []
        for block in doc[i].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    # Quantise the top edge so a line's spans sort together
                    # left-to-right rather than by sub-pixel drift.
                    page.append((round(span["bbox"][1] / 4), round(span["bbox"][0]),
                                 span["text"], span["font"], i + 1))
        page.sort(key=lambda r: (r[0], r[1]))
        rows.extend(page)

    out = collections.defaultdict(list)
    qnum = None
    j = 0
    while j < len(rows):
        head = QNUM_RE.match("\n" + rows[j][2])
        if head:
            qnum = int(head.group(1))
        if "image.axd" not in rows[j][2]:
            j += 1
            continue

        url = clean_url(rows[j][2]).lstrip("(")
        k = j + 1
        while k < len(rows) and not GOOD_URL.match(url):
            piece = unicodedata.normalize("NFKC", re.sub(r"\s+", "", rows[k][2]))
            if not piece or "glyphicons" in rows[k][3].lower():
                k += 1          # the broken-image mark itself, not the address
                continue
            if not CONT_RE.match(piece):
                break           # prose or a percentage: the address ended
            url += piece.rstrip(")")
            k += 1
        if GOOD_URL.match(url) and qnum:
            out[qnum].append((url, rows[j][4]))
        j = max(k, j + 1)
    return out


def flatten(text):
    """Words only, lowercased -- so a match survives the print's line wraps."""
    return re.sub(r"[^0-9a-z]+", " ",
                  unicodedata.normalize("NFKC", text or "").lower()).strip()


def question_blocks(doc):
    """
    The document cut into question blocks, once per reading order.

    A block runs from one "N." marker to the next, so it holds one question's
    stem, its options, and -- if it had one -- its figure address. Working in
    blocks is what makes the binding safe: an address can then only ever reach
    the question it is printed with.

    The two orderings are kept as SEPARATE lists rather than pooled, because
    sort=True moves where the markers fall: the same question can sit under
    "26." in one reading and "31." in the other, and pooling them made every
    such question look ambiguous and get dropped.
    """
    readings = []
    for sort in (False, True):
        parts, marks, pos = [], [], 0
        for i in range(doc.page_count):
            text = doc[i].get_text(sort=sort)
            parts.append(text)
            marks.append((pos, i + 1))
            pos += len(text)
        text = "".join(parts)

        cuts = [(m.start(), int(m.group(1))) for m in QNUM_RE.finditer(text)]
        blocks = []
        for idx, (begin, num) in enumerate(cuts):
            stop = cuts[idx + 1][0] if idx + 1 < len(cuts) else len(text)
            page = 1
            for mark, pnum in marks:
                if mark <= begin:
                    page = pnum
                else:
                    break
            body = text[begin:stop]
            urls = [u for u in (clean_url(mo.group(0))
                                for mo in URL_RE.finditer(body))
                    if GOOD_URL.match(u)]
            flat = flatten(body)
            if len(flat) > MAX_BLOCK:
                continue
            blocks.append({"num": num, "flat": flat,
                           "page": page, "urls": urls, "order": idx})
        readings.append(blocks)
    return readings


def locate(stem, options, blocks):
    """
    The block that IS this question, matched on its own words.

    The printed number cannot do this job. Each PDF carries several separately
    numbered sets -- the Cornea file alone has five different questions
    numbered 26 -- so binding by number handed one question's photograph to
    another's. Matching the text cannot drift that way.

    Returns [] when the question cannot be pinned down, which is the honest
    answer: a guess here silently corrupts the bank.
    """
    needle = flatten(stem)
    for size in (70, 55, 40, 30):
        probe = needle[:size]
        if len(probe) < 20:
            continue
        # The stem must OPEN the block, not merely appear in it. A block runs
        # stem-options-explanation, and an explanation quotes other questions:
        # the Horner block spells out "decreased levator function, lid lag on
        # downgaze..." to contrast it, which matched the congenital-ptosis
        # question and handed it the Horner photographs.
        hits = [b for b in blocks
                if 0 <= b["flat"].find(probe) <= STEM_AT]
        if not hits:
            continue
        if len(hits) > 1:
            # A stem like "What is the most likely diagnosis?" belongs to
            # dozens of questions; this question's own options tell them apart.
            texts = (list(options.values()) if isinstance(options, dict)
                     else list(options or []))
            keys = [flatten(o)[:34] for o in texts[:2] if len(flatten(o)) >= 12]
            if keys:
                tight = [b for b in hits if all(k in b["flat"] for k in keys)]
                if tight:
                    hits = tight
        # One question is printed twice -- in the question list, and again
        # above its explanation -- so several hits are expected and fine. What
        # is NOT fine is hits that are different questions, which show up as
        # more than one distinct printed number.
        if len({b["num"] for b in hits}) != 1:
            return []
        return hits
    return []


def addresses_for(q, readings):
    """
    Every address printed with this question, across both readings.

    Each reading is located on its own and only contributes if it pinned the
    question down; a reading that could not is simply silent rather than
    dragging in a neighbour's figure.
    """
    seen, out = set(), []
    placed = False
    for blocks in readings:
        hits = locate(q["question"], q.get("options"), blocks)
        if not hits:
            continue
        placed = True
        for h in hits:
            for u in h["urls"]:
                if u not in seen:
                    seen.add(u)
                    out.append((u, h["page"]))
    return out, placed


def cmd_map(args):
    import fitz

    mapping = pdf_map()
    banks = [args.bank] if args.bank else [b for b in sorted(mapping) if b.endswith("-bcsc")]
    plan = []
    for bank in banks:
        doc = fitz.open(os.path.join(ROOT, mapping[bank]))
        readings = question_blocks(doc)
        data = json.load(open(os.path.join(DATA, f"{bank}.json"), encoding="utf-8"))
        have = sum(1 for q in data if q.get("imageUrl"))
        matched = missing_now = unplaceable = 0
        for q in data:
            urls, placed = addresses_for(q, readings)
            if not placed:
                unplaceable += 1
                continue
            if not urls:
                continue
            matched += 1
            if q.get("imageUrl"):
                continue
            missing_now += 1
            plan.append({"bank": bank, "id": q["id"], "url": urls[0][0],
                         "page": urls[0][1],
                         # A question printed with two figures, or read two ways;
                         # kept so a dead first choice is not the end of it.
                         "extra": [u for u, _ in urls[1:]]})
        print(f"{bank:22s} {len(data):5d} questions, {have:4d} already have an image, "
              f"{matched:4d} are printed with an address, {missing_now:4d} of those "
              f"have no image now"
              + (f", {unplaceable} could not be pinned to one block" if unplaceable else ""))
        doc.close()

    path = os.path.join(AUDIT, "figure_recovery.json")
    json.dump(plan, io.open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print()
    print(f"{len(plan)} question(s) can be given a figure they currently lack")
    print(f"  written: {path}")


def cmd_repair(args):
    """
    Take back every figure that was bound to the wrong question.

    The first binding used the printed question number, which is not unique: a
    PDF carries several separately numbered sets, so the Cornea file alone has
    five different questions numbered 26. That handed one question's picture to
    another's -- a VZV question got a photograph of drug-induced conjunctival
    change. Anything whose address is not printed in its OWN block goes back.
    """
    import fitz

    mapping = pdf_map()
    banks = [args.bank] if args.bank else [b for b in sorted(mapping) if b.endswith("-bcsc")]
    kept = pulled = 0
    for bank in banks:
        doc = fitz.open(os.path.join(ROOT, mapping[bank]))
        readings = question_blocks(doc)
        path = os.path.join(DATA, f"{bank}.json")
        data = json.load(open(path, encoding="utf-8"))
        b_kept = b_pulled = 0
        for q in data:
            if not q.get("figureRecovered"):
                continue
            found, _ = addresses_for(q, readings)
            mine = {u for u, _ in found}
            name = os.path.basename(q.get("imageUrl") or "")
            dest = os.path.join(IMAGES, bank, name)
            # The file is named for the address it came from only indirectly,
            # so re-derive: a figure is legitimate exactly when this question's
            # own block prints at least one address and the file exists.
            if mine and os.path.exists(dest):
                b_kept += 1
                continue
            b_pulled += 1
            q.pop("imageUrl", None)
            q.pop("figureRecovered", None)
            if os.path.exists(dest) and not args.dry_run:
                os.remove(dest)
        if not args.dry_run:
            json.dump(data, io.open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        print(f"{bank:22s} kept {b_kept:4d}, took back {b_pulled:4d}"
              + ("  (dry run, nothing written)" if args.dry_run else ""))
        kept += b_kept
        pulled += b_pulled
        doc.close()
    print()
    print(f"{kept} figure(s) verified against their own block, {pulled} taken back")


# What the bytes actually are, regardless of what the address implies. The
# host serves a mix: 139 of the first 174 recovered figures were JPEG, and
# naming those ".png" would have left the bank describing its own files wrongly.
MAGIC = ((b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpg"),
         (b"GIF87a", "gif"), (b"GIF89a", "gif"))


def suffix(body):
    for magic, ext in MAGIC:
        if body.startswith(magic):
            return ext
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "webp"
    return None


def grab(url):
    """The bytes at this address, or None if it does not serve a picture."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
        time.sleep(0.25)                      # be gentle with the host
    except Exception as exc:
        return None, str(exc)
    if not ctype.startswith("image/") or len(body) < 2000:
        return None, f"served {ctype or 'nothing'}, {len(body)}B"
    if suffix(body) is None:
        return None, f"claimed {ctype} but the bytes are not a picture"
    return body, None


def cmd_fetch(args):
    plan = json.load(open(os.path.join(AUDIT, "figure_recovery.json"), encoding="utf-8"))
    rows = [r for r in plan if not args.bank or r["bank"] == args.bank]
    if args.limit:
        rows = rows[:args.limit]

    by_bank = collections.defaultdict(list)
    for r in rows:
        by_bank[r["bank"]].append(r)

    for bank, items in sorted(by_bank.items()):
        folder = os.path.join(IMAGES, bank)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(DATA, f"{bank}.json")
        data = json.load(open(path, encoding="utf-8"))
        by_id = {q["id"]: q for q in data}
        ok = fail = extras = 0
        for r in items:
            q = by_id.get(r["id"])
            if q is None or q.get("imageUrl"):
                continue

            # A question can be printed with more than one figure, and they only
            # make sense together: the third-nerve-palsy question shows the same
            # patient twice, in primary gaze and with the lid ptotic. Taking
            # only the first would have thrown half of that away.
            got = []
            for pos, cand in enumerate([r["url"]] + (r.get("extra") or [])):
                stem = f"p{r['page']}_recovered{r['id']}" + (f"_{pos}" if pos else "")
                have = [e for e in ("png", "jpg", "gif", "webp")
                        if os.path.exists(os.path.join(folder, f"{stem}.{e}"))]
                if have:
                    got.append(f"/images/{bank}/{stem}.{have[0]}")
                    continue
                body, why = grab(cand)
                if body is None:
                    print(f"  id {r['id']} figure {pos + 1}: {why}")
                    continue
                name = f"{stem}.{suffix(body)}"
                with open(os.path.join(folder, name), "wb") as fh:
                    fh.write(body)
                got.append(f"/images/{bank}/{name}")

            if not got:
                fail += 1
                print(f"  id {r['id']}: no address returned a picture")
                continue

            q["imageUrl"] = got[0]
            q["figureRecovered"] = True
            if len(got) > 1:
                rest = [u for u in got[1:] if u not in (q.get("imageUrls") or [])]
                q["imageUrls"] = (q.get("imageUrls") or []) + rest
                extras += len(rest)
            ok += 1

        if not args.dry_run:
            json.dump(data, io.open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        print(f"{bank}: {ok} figure(s) attached"
              + (f" (+{extras} further panel(s))" if extras else "")
              + f", {fail} failed"
              + ("  (dry run, nothing written)" if args.dry_run else ""))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("map"); m.add_argument("bank", nargs="?"); m.set_defaults(func=cmd_map)
    r = sub.add_parser("repair"); r.add_argument("bank", nargs="?")
    r.add_argument("--dry-run", action="store_true"); r.set_defaults(func=cmd_repair)
    f = sub.add_parser("fetch"); f.add_argument("bank", nargs="?")
    f.add_argument("--limit", type=int); f.add_argument("--dry-run", action="store_true")
    f.set_defaults(func=cmd_fetch)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
