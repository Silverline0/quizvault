#!/usr/bin/env python3
"""
Parse the Anterior Segment quiz into a bank file.

The source is a purpose-written answer key rather than a scanned recall sheet,
so it needs none of the salvage the other parsers do.  Two things about it do
need care.

First, the correct option is not marked inline.  The tick is printed on its OWN
line directly after the option it belongs to --

    A. Tear film and atmosphere
    ✓
    B. Aqueous humor

-- or rather, that is how it reads in the extracted text.  On the page the tick
actually sits on the SAME line as its option, just to the left and a couple of
points higher, and it is that height difference that decides whether the
extractor emits it before or after.  For 43 of the 45 it lands after; for two
it lands before, and reading order alone silently loses their key or gives it
to the wrong option.  So a tick is matched to the option line it is vertically
nearest to, which is what the eye does and cannot be thrown by the ordering.

Second, the author has written notes back into the document, in blue Times New
Roman against the body's grey Liberation Sans.  They are not explanation: they
are the author arguing with the key -- "Both answers A and C could be correct
... I'll go with A" on a question marked C.  Reading them as part of the
explanation would bury a stated disagreement inside the text that is supposed
to justify the answer, so they are pulled out by font and kept as a note of
their own.

    python scripts/parse_as_quiz.py --dry-run
    python scripts/parse_as_quiz.py
"""

import argparse
import io
import json
import os
import re
import sys
import unicodedata

import fitz

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "AS Quiz Full Answers.pdf")
DATA = os.path.join(ROOT, "public", "data")
SET_ID = "anterior-segment-quiz"

Q_OPEN = re.compile(r"^\s*(\d{1,3})\.\s+(?=\S)")
OPT = re.compile(r"^\s*([A-E])\.\s+(\S.*?)\s*$")
TICK = re.compile(r"^\s*[✓✔✅]\s*$")
EXPL = re.compile(r"^\s*Explanation\s*:\s*(.*)$")
# The author's own hand. Everything else in the document is Liberation Sans.
ANNOTATION_FONT = "TimesNewRoman"


def lines_with_kind():
    """
    The document as ordered lines: the text, whether it is the author's own
    note, and the vertical middle of the line.

    Working from spans rather than flat text does two jobs. It is what makes
    the note separable -- notes and body are interleaved in reading order and
    only the font tells them apart -- and it keeps the geometry the tick needs.
    """
    doc = fitz.open(PDF)
    out = []
    for i in range(doc.page_count):
        rows = []
        for block in doc[i].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(sp["text"] for sp in line["spans"])
                if not text.strip():
                    continue
                note = any(sp["font"].startswith(ANNOTATION_FONT)
                           for sp in line["spans"] if sp["text"].strip())
                y0, y1 = line["bbox"][1], line["bbox"][3]
                rows.append({"y": (y0 + y1) / 2, "page": i,
                             "text": unicodedata.normalize("NFKC", text),
                             "note": note})
        rows.sort(key=lambda r: r["y"])
        out.extend(rows)
    doc.close()
    return out


def join(parts):
    return " ".join(p.strip() for p in parts if p.strip())


def parse_block(rows):
    """One question's lines into stem, options, key, explanation and note."""
    stem, opts, expl, note = [], {}, [], []
    option_rows, tick_rows = [], []
    in_expl = False

    for row in rows:
        text = row["text"]
        if row["note"]:
            note.append(text)
            continue
        mo = EXPL.match(text)
        if mo:
            in_expl = True
            if mo.group(1).strip():
                expl.append(mo.group(1))
            continue
        if in_expl:
            expl.append(text)
            continue
        mo = OPT.match(text)
        if mo:
            opts[mo.group(1)] = mo.group(2).strip()
            option_rows.append((row["y"], row["page"], mo.group(1)))
            continue
        if TICK.match(text):
            tick_rows.append((row["y"], row["page"]))
            continue
        if not opts:
            stem.append(text)

    # The tick belongs to whichever option it sits level with, on its own page.
    answer = None
    for ty, tpage in tick_rows:
        near = [(abs(oy - ty), letter)
                for oy, opage, letter in option_rows if opage == tpage]
        if near:
            answer = min(near)[1]

    return join(stem), opts, answer, join(expl), join(note)


def parse():
    rows = lines_with_kind()
    starts = [i for i, r in enumerate(rows)
              if not r["note"] and Q_OPEN.match(r["text"])]
    out = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(rows)
        number = int(Q_OPEN.match(rows[start]["text"]).group(1))
        block = [dict(r) for r in rows[start:end]]
        # Drop the number from the first line so it does not sit in the stem.
        block[0]["text"] = Q_OPEN.sub("", block[0]["text"], count=1)
        stem, opts, answer, expl, note = parse_block(block)
        out.append({"number": number, "question": stem, "options": opts,
                    "correctAnswer": answer, "explanation": expl,
                    "sourceNote": note})
    return out


def check(rows):
    problems = []
    for r in rows:
        why = []
        if not r["question"]:
            why.append("no stem")
        if len(r["options"]) < 2:
            why.append(f"{len(r['options'])} option(s)")
        if not r["correctAnswer"]:
            why.append("no key")
        elif r["correctAnswer"] not in r["options"]:
            why.append(f"key {r['correctAnswer']} is not among the options")
        if not r["explanation"]:
            why.append("no explanation")
        if why:
            problems.append((r["number"], "; ".join(why)))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = parse()
    numbers = [r["number"] for r in rows]
    gaps = [n for n in range(1, (max(numbers) if numbers else 0) + 1)
            if n not in numbers]
    problems = check(rows)
    noted = [r for r in rows if r["sourceNote"]]

    print(f"{len(rows)} question(s) parsed")
    print(f"  numbering runs 1-{max(numbers) if numbers else 0}"
          + (f", missing {gaps}" if gaps else ", with no gaps"))
    print(f"  {len(problems)} question(s) incomplete")
    for n, why in problems[:12]:
        print(f"    #{n}: {why}")
    print(f"  {len(noted)} question(s) carry a note from the author")
    for r in noted:
        print(f"    #{r['number']} (key {r['correctAnswer']}): {r['sourceNote'][:88]}")

    if args.dry_run:
        return

    bank = [{
        "id": r["number"],
        "source": SET_ID,
        "question": r["question"],
        "options": r["options"],
        "correctAnswer": r["correctAnswer"],
        "explanation": r["explanation"],
        "subspecialty": "Anterior Segment",
        **({"sourceNote": r["sourceNote"]} if r["sourceNote"] else {}),
    } for r in rows]

    path = os.path.join(DATA, f"{SET_ID}.json")
    json.dump(bank, io.open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"  written: {path}")


if __name__ == "__main__":
    main()
