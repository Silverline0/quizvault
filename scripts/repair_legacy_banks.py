#!/usr/bin/env python3
"""
Repair three malformed records in the pre-existing question banks.

All three predate the Promotion Exam work and all three are user-visible:

  cornea-oq #151, #337 -- `options` is empty and `correctAnswer` points at a
      choice that is not there, so the card renders with no answer buttons and
      cannot be answered at all.  The original import put the real question,
      its four choices and the answer key into the `explanation` field, in the
      shape "<question> A.<x> B.<x> C.<x> D.<x> A:<letter> <discussion>".
      Everything needed is therefore already in the record.

  uveitis-bcsc #35 -- choices A and C were dropped on import, leaving B and D
      with `correctAnswer: "A"`.  The card is always scored wrong.  The full
      item is recovered from scripts/raw_uveitis_bcsc.txt, the extraction the
      bank was built from.

Nothing here is invented: each field is copied from the record itself or from
the raw source text.  Run with --dry-run first; a .bak is written before any
file is changed.

Usage:  python scripts/repair_legacy_banks.py [--dry-run]
"""

import argparse
import io
import json
import os
import re
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "public", "data")
RAW_UVEITIS = os.path.join(ROOT, "scripts", "raw_uveitis_bcsc.txt")

# "<stem> A.<a> B.<b> C.<c> D.<d> A:<key> <discussion>"
INLINE_ITEM_RE = re.compile(
    r"^(?P<stem>.*?)"
    r"\s+A\s*[.)]\s*(?P<a>.+?)"
    r"\s+B\s*[.)]\s*(?P<b>.+?)"
    r"\s+C\s*[.)]\s*(?P<c>.+?)"
    r"\s+D\s*[.)]\s*(?P<d>.+?)"
    r"\s+A\s*:\s*(?P<key>[A-D])\b\s*"
    r"(?P<rest>.*)$",
    re.S)


def norm(t):
    return re.sub(r"\s+", " ", t or "").strip()


def repair_inline(q):
    """cornea-oq: recover choices and key that were flattened into explanation."""
    m = INLINE_ITEM_RE.match(q.get("explanation") or "")
    if not m:
        return None
    stem = norm(q.get("question", ""))
    tail = norm(m.group("stem"))
    # The vignette sits in `question`; the actual ask is at the head of the
    # explanation.  Join them so the card reads as one question.
    full = f"{stem} {tail}".strip() if tail else stem
    options = {k.upper(): norm(m.group(k)) for k in ("a", "b", "c", "d")}
    if not all(options.values()):
        return None
    key = m.group("key").upper()
    if key not in options:
        return None
    return {"question": full, "options": options, "correctAnswer": key,
            "explanation": norm(m.group("rest")) or q.get("explanation", "")}


def repair_uveitis_35(q):
    """Recover the two dropped choices and the full stem from the raw source."""
    if not os.path.exists(RAW_UVEITIS):
        return None
    raw = io.open(RAW_UVEITIS, encoding="utf-8", errors="replace").read()
    anchor = raw.find("intracranial lesions characterized")
    if anchor < 0:
        return None
    window = raw[max(0, anchor - 900):anchor + 900].replace("\xa0", " ")

    # The export lists each choice's text on the line BEFORE its letter:
    #     60%-70%
    #     A.
    #     50% Correct
    found = {}
    for text, letter in re.findall(r"\n([^\n]{2,40})\n([A-D])\.\n", window):
        found[letter.strip()] = text.strip()
    if not {"A", "B", "C", "D"} <= set(found):
        return None

    stem_start = window.find("A 65-year-old")
    stem_end = window.find("same cells?")
    stem = norm(window[stem_start:stem_end + len("same cells?")]) if stem_start >= 0 else None
    if not stem:
        return None

    options = {k: norm(found[k]) for k in "ABCD"}
    if norm(q["options"].get("B", "")) and norm(q["options"]["B"]).lower() \
            not in options["B"].lower():
        return None                      # source and bank disagree -- do not touch
    return {"question": stem, "options": options, "correctAnswer": "A"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changes = []

    # ---- cornea-oq ----------------------------------------------------
    path = os.path.join(DATA, "cornea-oq.json")
    data = json.load(io.open(path, encoding="utf-8"))
    touched = False
    for q in data:
        if isinstance(q.get("options"), dict) and not q["options"]:
            fix = repair_inline(q)
            if not fix:
                changes.append(("cornea-oq", q["id"], "NOT REPAIRABLE"))
                continue
            q.update(fix)
            touched = True
            changes.append(("cornea-oq", q["id"],
                            f"{len(fix['options'])} choices restored, key {fix['correctAnswer']}"))
    if touched and not args.dry_run:
        shutil.copyfile(path, path + ".bak")
        json.dump(data, io.open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    # ---- uveitis-bcsc --------------------------------------------------
    path = os.path.join(DATA, "uveitis-bcsc.json")
    data = json.load(io.open(path, encoding="utf-8"))
    touched = False
    for q in data:
        if isinstance(q.get("options"), dict) and q["options"] \
                and q.get("correctAnswer") not in q["options"]:
            fix = repair_uveitis_35(q) if q["id"] == 35 else None
            if not fix:
                changes.append(("uveitis-bcsc", q["id"], "NOT REPAIRABLE"))
                continue
            q.update(fix)
            touched = True
            changes.append(("uveitis-bcsc", q["id"],
                            f"choices A/C restored ({fix['options']['A']!r}, "
                            f"{fix['options']['C']!r}), key A now valid"))
    if touched and not args.dry_run:
        shutil.copyfile(path, path + ".bak")
        json.dump(data, io.open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    for bank, qid, note in changes:
        print(f"  {bank} #{qid}: {note}")
    if not changes:
        print("  nothing to repair")
    elif args.dry_run:
        print("\ndry run: no files written")


if __name__ == "__main__":
    main()
