#!/usr/bin/env python3
"""
Recover the promotion recalls that the parser walked past.

The bank holds fewer recalls than the PDF prints.  The originals are all still
there -- the parser simply did not pick them up, mostly because the recalls are
numbered inconsistently ("13-", "22.", "7)") and it recognised only one of
those spellings.  The 2023 pages number with a dash throughout, which is why a
whole year came up empty.

Every page of a year is cut into numbered recalls and each is matched against
what the bank already carries.  Matching is on the stem's words rather than its
number, for two reasons: the bank never recorded the printed number, and the
same numbers recur in every year.  The comparison also runs across ALL the
promotion files, not just the year in hand, because the parser did not reliably
file a recall under the year whose pages it was printed on -- the amiodarone
recall sits on a 2025 page but was published under 2024, and a year-local check
would have added it a second time.

What comes back is uneven, and deliberately kept that way.  Some pages are
clean text; others are photographs of an annotated print-out where the only
readable thing is the page itself.  So every recovered recall carries its page
scan, and the ones with no answer key or no options go to the unkeyed file
rather than being dressed up as answerable questions.

    python scripts/promo_recover.py scan 2025          # what is missing
    python scripts/promo_recover.py apply 2021 2022 2023 2024 2025
"""

import argparse
import collections
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# parse_promotion re-wraps stdout on import; leave its wrapper alone, because
# swapping the original back drops the last reference to it and the buffer
# underneath gets closed when it is collected.
import parse_promotion as P            # noqa: E402
import fitz                            # noqa: E402

DATA = os.path.join(ROOT, "public", "data")
AUDIT = os.path.join(ROOT, "scripts", "audit")
SCANS = os.path.join(ROOT, "public", "images", "promotion-pages")

# A recall opens with its number and any of three separators. Getting this
# wrong is the whole reason the bank is short.
Q_OPEN = re.compile(r"(?:^|\n)[ \t]*(\d{1,3})[ \t]*[.)\-]\s", re.M)
# An option on its own line. The separator is REQUIRED. Making it optional
# looked harmless and quietly ate stems: "A patient with globe trauma. Which
# of the following..." parsed as option A = "patient with globe trauma",
# leaving the question with no text at all. "A" is an English article before
# it is ever an option label.
OPT_LINE = re.compile(r"(?m)^[ \t]*([A-Ea-e])[ \t]*[.)\-][ \t]*(\S.*?)[ \t]*$")
# Options run together on one line: "A At the limbus B To the centre C ...".
OPT_INLINE = re.compile(r"(?:(?<=\s)|^)([A-Ea-e])[ \t]*[.)\-][ \t]*")
ANS = re.compile(r"\bAnswers?\s*[:\-]?\s*([A-Ea-e])\b")
# "Answer: A vs B" -- the recallers themselves disagreed. Recording only the
# first would state a key the source does not actually claim.
ANS_SPLIT = re.compile(r"\bAnswers?\s*[:\-]?\s*([A-Ea-e])\s*(?:vs\.?|/|or)\s*([A-Ea-e])\b", re.I)
# Headers the print puts between recalls; not part of any stem.
NOISE = re.compile(r"^(anterior segment|cornea|retina|uveitis|glaucoma|neuro|"
                   r"oculoplastics?|pediatrics?|optics|lens|cataract|pathology|"
                   r"general|miscellaneous|others?)\s*:?\s*$", re.I)


def flat(text):
    return re.sub(r"[^0-9a-z]+", " ", (text or "").lower()).strip()


def year_of_page(doc):
    """page -> exam year, decided exactly as the parser does."""
    fixed = {}
    for start, end, year in P.SECTIONS:
        if year:
            for pg in range(start, end + 1):
                fixed[pg] = year
    out, current = {}, None
    for i in range(doc.page_count):
        page = i + 1
        if fixed.get(page):
            current = fixed[page]
        try:
            for ln in P.classify(P.extract_lines(doc, i)):
                if getattr(ln, "kind", None) == "year":
                    current = ln.key
        except Exception:
            pass
        out[page] = current or "unknown"
    return out


def ascending_run(found):
    """
    Keep only markers that actually form an option list: A, then B, then C.

    Without this a stray "A" mid-sentence, or the "D" of a previous recall
    bleeding in, becomes an option and the question reads as nonsense.
    """
    want = "ABCDE"
    kept, expect = [], 0
    for pos, letter, text in found:
        if expect < len(want) and letter == want[expect]:
            kept.append((pos, letter, text))
            expect += 1
    return kept


def find_options(body):
    """
    This recall's options, taken however the print happens to lay them out.

    A single option counts. These are recalls, not a printed paper: the person
    writing them down often remembered one choice and the key, and nothing
    else. Refusing to split one option left it stuck on the end of the stem --
    "BRVO predictive investigation of visual outcome: A. FFA to look for extent
    of ischemia" -- which reads as neither a clean question nor a choice.
    Whether a recall is answerable is decided separately, and does need two.
    """
    line = ascending_run([(m.start(), m.group(1).upper(), m.group(2).strip())
                          for m in OPT_LINE.finditer(body)])
    if line:
        return {l: t for _, l, t in line}, line[0][0]

    marks = ascending_run([(m.start(), m.group(1).upper(), "")
                           for m in OPT_INLINE.finditer(body)])
    if marks:
        opts = {}
        for idx, (pos, letter, _) in enumerate(marks):
            stop = marks[idx + 1][0] if idx + 1 < len(marks) else len(body)
            end = OPT_INLINE.match(body, pos)
            opts[letter] = body[end.end():stop].strip() if end else ""
        opts = {k: v for k, v in opts.items() if v}
        if opts:
            return opts, marks[0][0]

    return {}, len(body)


def split_recall(body):
    """A recall's body into stem, options and answer."""
    answer, contested = None, None
    split = ANS_SPLIT.search(body)
    if split:
        contested = [split.group(1).upper(), split.group(2).upper()]
        body = body[:split.start()]
    else:
        mo = ANS.search(body)
        if mo:
            answer = mo.group(1).upper()
            body = body[:mo.start()]

    opts, first = find_options(body)
    stem = " ".join(
        ln.strip() for ln in body[:first].splitlines()
        if ln.strip() and not NOISE.match(ln.strip())
    ).strip()
    return stem, opts, answer, contested


# Words that mark a question even when the print lost the question mark.
ASKS = re.compile(r"\b(what|which|who|whom|whose|how|why|when|where|asking|"
                  r"ask|diagnosis|management|manage|treatment|treat|next step|"
                  r"most likely|best|cause|mechanism|complication|indicated|"
                  r"appropriate|investigation|finding|true|false|except)\b", re.I)


def looks_like_a_recall(stem, opts, answer):
    """
    Is there a question here, or only print noise?

    Three things come back from these pages that are not recalls, and each
    needed its own test.

    Photographs of an annotated hand-written print-out leave gibberish behind
    the image -- "L 6.Foil I VE, toeflocrious, mexifoc" -- which is caught by
    how little of it is real words.

    Pages OCR'd without spaces give the opposite shape, one enormous token per
    phrase: "evaluatethestabilityoftearfilm". Those read as perfectly solid
    words, so they are caught on token length instead.

    And a few pages are atlas plates whose captions are fluent prose about a
    photograph -- "The histologic photograph from a case of PAM shows nests of
    melanocytes" -- real sentences, but nobody's exam question. A recall
    always shows at least one of: a question mark, an answer key, an option,
    or a word that asks something.
    """
    tokens = [w for w in re.findall(r"[A-Za-z]+", stem) if len(w) >= 3]
    letters = sum(c.isalpha() for c in stem)

    if tokens:
        # Gibberish is punctuation and stray letters, so real words carry little.
        if sum(len(w) for w in tokens) / max(1, letters) < 0.55:
            return False
        # Lost spaces show up as an implausible average word length.
        if sum(len(w) for w in tokens) / len(tokens) > 11:
            return False

    asks = ("?" in stem) or bool(answer) or bool(opts) or bool(ASKS.search(stem))
    if not asks:
        return False

    if opts:
        return True
    if not tokens:
        return bool(answer)          # a bare key still records that one existed
    if answer and letters >= 15:
        return True
    return letters >= 40 and len(tokens) >= 6


def subspecialty_at(text, upto):
    """The last subspecialty header printed before this point on the page."""
    best = None
    for mo in re.finditer(r"(?m)^[ \t]*([A-Za-z /&-]{3,30})[ \t]*:[ \t]*$", text[:upto]):
        key = mo.group(1).strip().lower()
        if key in P.SUBSPECIALTIES:
            best = P.SUBSPECIALTIES[key]
    return best


def bank_stems():
    """Every stem the bank already carries, across every promotion file."""
    import glob
    out = []
    for path in glob.glob(os.path.join(DATA, "promotion-*.json")):
        for q in json.load(open(path, encoding="utf-8")):
            stem = flat(q.get("question"))
            if stem:
                out.append((stem, set(stem.split())))
    return out


def already_have(stem, published):
    """Is this recall one the bank already carries, under any year?"""
    needle = flat(stem)
    if len(needle) < 12:
        return False                 # too thin to claim a match either way
    words = set(needle.split())
    for have, hwords in published:
        short, long_ = sorted((needle, have), key=len)
        if short[:60] in long_:
            return True
        # The parser often clipped a stem, so a prefix test alone misses it;
        # shared vocabulary catches a clipped or lightly reworded copy.
        if len(words & hwords) / max(1, min(len(words), len(hwords))) >= 0.75:
            return True
    return False


def scan(doc, years, want):
    published = bank_stems()
    missing = []
    for i in range(doc.page_count):
        page = i + 1
        year = years[page]
        if want and year not in want:
            continue
        text = doc[i].get_text()
        for mo in Q_OPEN.finditer(text):
            num = int(mo.group(1))
            nxt = Q_OPEN.search(text, mo.end())
            body = text[mo.end():nxt.start() if nxt else len(text)]
            stem, opts, answer, contested = split_recall(body)
            if already_have(stem, published):
                continue
            if not looks_like_a_recall(stem, opts, answer or (contested or [None])[0]):
                continue
            missing.append({
                "year": year, "pdfPage": page, "printedNumber": num,
                "question": stem, "options": opts, "correctAnswer": answer,
                "contestedAnswer": contested,
                "subspecialty": subspecialty_at(text, mo.start()),
                # Answerable means the reader can actually sit it as a question:
                # a key and something to choose between. The rest are still
                # real recalls, and go to the unkeyed file to be read.
                "answerable": bool(answer and len(opts) >= 2),
            })
    return missing


def report(missing):
    per = collections.Counter(m["year"] for m in missing)
    keyed = collections.Counter(m["year"] for m in missing if m["answerable"])
    print(f"{'year':>6} {'recovered':>10} {'answerable':>11} {'to read only':>13}")
    for year in sorted(per):
        print(f"{year:>6} {per[year]:10d} {keyed[year]:11d} {per[year]-keyed[year]:13d}")
    print()
    print(f"  {len(missing)} recall(s) the bank does not have")


def cmd_scan(args):
    doc = fitz.open(P.PDF)
    missing = scan(doc, year_of_page(doc), set(args.years))
    report(missing)
    path = os.path.join(AUDIT, "promo_missing.json")
    json.dump(missing, io.open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"  written: {path}")
    for m in missing[:8]:
        print(f"    {m['year']} p{m['pdfPage']} #{m['printedNumber']} "
              f"{'[keyed]' if m['answerable'] else '[read]  '} "
              f"{m['question'][:70]}")


def render_scans(doc, pages, dpi=105):
    """The page behind each recovered recall, so it can be read as printed."""
    os.makedirs(SCANS, exist_ok=True)
    made = 0
    zoom = dpi / 72.0
    for page in sorted(pages):
        dest = os.path.join(SCANS, f"page_{page:03d}.jpg")
        if os.path.exists(dest):
            continue
        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        pix.save(dest, jpg_quality=80)
        made += 1
    return made


NOTE_FULL = ("Recovered from the source PDF: the original parser skipped it because "
             "of how its number was printed. Wording is the recall as written; "
             "the page scan shows it as printed.")
NOTE_PART = ("Recovered from the source PDF, which records this recall only in "
             "part -- the person writing it down kept the gist and not every "
             "choice. Nothing here has been invented to fill the gaps: read it "
             "from the page scan.")
NOTE_NOKEY = ("Recovered from the source PDF, which gives no answer for it. No "
              "key has been guessed, so this one is here to read rather than to "
              "sit. The page scan shows it as printed.")


def cmd_apply(args):
    doc = fitz.open(P.PDF)
    missing = scan(doc, year_of_page(doc), set(args.years))
    report(missing)
    if not missing:
        return

    made = render_scans(doc, {m["pdfPage"] for m in missing})
    print(f"  {made} page scan(s) rendered")

    # Everything goes under the year it was printed in. The unkeyed file is for
    # recalls whose key had to be supplied -- every entry in it carries one --
    # and these do not: filing them there would mean either inventing an answer
    # or leaving that file inconsistent with itself.
    by_year = collections.defaultdict(list)
    for m in missing:
        by_year[f"promotion-{m['year']}"].append(m)

    counts = {}
    for name, rows in sorted(by_year.items()):
        path = os.path.join(DATA, f"{name}.json")
        data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
        next_id = max((q["id"] for q in data if isinstance(q.get("id"), int)),
                      default=0) + 1
        for m in sorted(rows, key=lambda r: (r["pdfPage"], r["printedNumber"])):
            if m["answerable"]:
                note = NOTE_FULL
            elif m["correctAnswer"] or m.get("contestedAnswer"):
                note = NOTE_PART
            else:
                note = NOTE_NOKEY
            row = {
                "id": next_id,
                "source": name,
                "question": m["question"] or
                            f"Recall {m['printedNumber']} on page {m['pdfPage']}, "
                            f"printed as a picture with no readable text. "
                            f"See the page scan.",
                "options": m["options"],
                "correctAnswer": m["correctAnswer"],
                "explanation": None,
                "year": m["year"],
                "subspecialty": m["subspecialty"],
                "pdfPage": m["pdfPage"],
                "pageScanUrl": f"/images/promotion-pages/page_{m['pdfPage']:03d}.jpg",
                "recoveredFromPage": True,
                "sourceNote": note,
            }
            if m.get("contestedAnswer"):
                # The source itself says "Answer: A vs B". Recording one of them
                # as the key would assert something it does not claim.
                row["contested"] = True
                row["contestedAnswers"] = m["contestedAnswer"]
            data.append(row)
            next_id += 1
        if not args.dry_run:
            json.dump(data, io.open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        counts[name] = len(data)
        print(f"  {name}: +{len(rows)} -> {len(data)}")

    # The manifest is what the site reads to build its list, so a count left
    # stale there makes recovered recalls invisible in the picker.
    mpath = os.path.join(DATA, "manifest.json")
    man = json.load(open(mpath, encoding="utf-8"))
    for entry in man.get("questionSets", []):
        if entry.get("id") in counts:
            entry["questionCount"] = counts[entry["id"]]
    if not args.dry_run:
        json.dump(man, io.open(mpath, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("  manifest counts updated" + ("  (dry run, nothing written)"
                                         if args.dry_run else ""))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("years", nargs="*")
    s.set_defaults(func=cmd_scan)
    a = sub.add_parser("apply"); a.add_argument("years", nargs="*")
    a.add_argument("--dry-run", action="store_true"); a.set_defaults(func=cmd_apply)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
