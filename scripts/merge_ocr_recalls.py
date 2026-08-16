#!/usr/bin/env python3
"""
Merge transcribed screenshot-only recalls into the Promotion Exam banks.

Some recalls in the source exist only as a pasted screenshot -- stem, choices and
answer all live inside the image, leaving nothing in the PDF's text layer, so
`parse_promotion.py` cannot reach them.  Those images were transcribed
separately; this folds the usable results back into the banks.

Acceptance is deliberately narrow, because a fabricated option or an invented
answer key in board-prep material is worse than a missing question:

  * the transcription must be classified as a question, with >= 2 choices
  * the answer must be VISIBLY marked in the image -- never inferred
  * the marked answer must correspond to a real choice
  * low-confidence transcriptions are refused outright
  * choices that are bare figure labels ("A", "B", "C") are kept, since the
    record carries the panel they point at, but are annotated as such
  * verbatim duplicates are collapsed

An answer is only ever taken from a marker visible in that same image.  A letter
appearing in a neighbouring screenshot is not evidence for this one.

Everything refused is written to a report rather than dropped silently.

Usage:  python scripts/merge_ocr_recalls.py [--dry-run]
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
DATA = os.path.join(ROOT, "public", "data")
REPORT_DIR = os.environ.get("PROMO_REPORT", os.path.join(ROOT, "scripts"))
OCR_DIR = os.environ.get("OCR_DIR", os.path.join(REPORT_DIR, "ocr"))

PROVENANCE = "Transcribed from a screenshot in the source document."
DISPUTE_RE = re.compile(r"\bdisput|\bwrong\b|\bincorrect\b|contradic", re.I)


# The source numbers its recalls; that number is part of the document, not part
# of the question, and 30 of 32 transcriptions already dropped it.
LEADING_NUM_RE = re.compile(r"^\s*\d{1,3}\s*[-.):]\s+(?=\S)")
FIGURE_LABEL_NOTE = ("The choices are the labelled panels in the image above.")


def norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def strip_leading_number(text):
    return LEADING_NUM_RE.sub("", text).strip()


def page_context(root):
    """year and subspecialty in force at each PDF page, from the parser."""
    sys.path.insert(0, os.path.join(root, "scripts"))
    import fitz
    import parse_promotion as P

    doc = fitz.open(P.PDF)
    years, subs = {}, {}
    cy, cs = None, None
    fixed = {}
    for start, end, default_year in P.SECTIONS:
        for p in range(start, end + 1):
            fixed[p] = default_year
    for i in range(doc.page_count):
        page = i + 1
        if fixed.get(page):
            cy = fixed[page]
        for ln in P.classify(P.extract_lines(doc, i)):
            if ln.kind == "year":
                cy = ln.key
            elif ln.kind == "subspec":
                cs = ln.key
        years[page] = cy or "unknown"
        subs[page] = cs or "Miscellaneous"
    return years, subs


def synth_task(task_id, image_url, years, subs):
    """
    Rebuild a task for a transcription whose work-list entry no longer exists.

    The work list is regenerated whenever the parser runs, and improvements to
    figure binding legitimately shrink it -- but a transcription already done
    should not be thrown away just because its entry moved.
    """
    m = re.match(r"p(\d+)_", os.path.basename(image_url))
    page = int(m.group(1)) if m else 0
    return {"pdfPage": page, "imageUrl": image_url,
            "year": years.get(page, "unknown"),
            "subspecialty": subs.get(page, "Miscellaneous")}


def load_tasks():
    tasks = {}
    for path in sorted(glob.glob(os.path.join(OCR_DIR, "batch_*.json"))):
        with open(path, encoding="utf-8") as fh:
            for t in json.load(fh):
                tasks[t["task_id"]] = t
    return tasks


def load_results():
    rows = []
    for path in sorted(glob.glob(os.path.join(OCR_DIR, "result_*.json"))):
        with open(path, encoding="utf-8") as fh:
            rows.extend(json.load(fh))
    return rows


def judge(r, task):
    """Return (accepted, reason)."""
    if r.get("type") != "question":
        return False, f"not a question ({r.get('type')})"
    if (r.get("confidence") or "").lower() == "low":
        return False, "low-confidence transcription"
    opts = {k: norm(v) for k, v in (r.get("options") or {}).items() if norm(v)}
    if len(opts) < 2:
        return False, "fewer than 2 legible options"
    # Choices that are bare panel labels ("A", "B", ...) only make sense next to
    # the figure -- which the record does carry -- so they are kept and
    # annotated rather than discarded.
    ans = (r.get("answer") or "").strip().upper()
    if not ans:
        return False, "no answer visibly marked in the image"
    if ans not in opts:
        return False, f"marked answer {ans!r} is not one of the choices"
    if not norm(r.get("question")):
        return False, "no stem"
    if not task:
        return False, "no matching source task"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tasks = load_tasks()
    results = load_results()
    years, subs = page_context(ROOT)
    print(f"{len(results)} transcriptions, {len(tasks)} source images")

    accepted, refused, seen = [], [], {}
    url_by_task = {t["task_id"]: t["imageUrl"] for t in tasks.values()}
    for r in results:
        task = tasks.get(r["task_id"])
        if task is None:
            url = url_by_task.get(r["task_id"]) or r.get("imageUrl")
            if url:
                task = synth_task(r["task_id"], url, years, subs)
        ok, reason = judge(r, task)
        if not ok:
            refused.append({"task_id": r["task_id"], "type": r.get("type"),
                            "reason": reason, "notes": r.get("notes", "")})
            continue

        opts = {k: norm(v) for k, v in r["options"].items() if norm(v)}
        # Signature matches the text-layer parser's: compare the *stripped*
        # stem, and scope it to the year.  The source genuinely re-uses recalls
        # across sittings, and someone drilling 2024 should still see a question
        # that also appeared in 2018.
        sig = (task["year"],
               strip_leading_number(norm(r["question"])).lower(),
               tuple(sorted(v.lower() for v in opts.values())))
        if sig in seen:
            refused.append({"task_id": r["task_id"], "type": "question",
                            "reason": f"duplicate of {seen[sig]}",
                            "notes": r.get("notes", "")})
            continue
        seen[sig] = r["task_id"]

        parts = []
        if all(len(norm(v)) <= 2 for v in opts.values()):
            parts.append(FIGURE_LABEL_NOTE)
        if norm(r.get("explanation")):
            parts.append(norm(r["explanation"]))
        notes = norm(r.get("notes"))
        if notes and DISPUTE_RE.search(notes):
            # The compiler sometimes argues with the marking in the margin.
            # Surface that rather than presenting the key as settled.
            parts.append(f"Note on the source's marking: {notes}")
        parts.append(PROVENANCE)

        if all(len(v) <= 2 for v in opts.values()):
            parts_extra = FIGURE_LABEL_NOTE
        else:
            parts_extra = ""

        accepted.append({
            "year": task["year"],
            "subspecialty": task.get("subspecialty") or subs.get(task["pdfPage"],
                                                                 "Miscellaneous"),
            "pdfPage": task["pdfPage"],
            "imageUrl": task["imageUrl"],
            "figureLabelNote": parts_extra,
            "question": strip_leading_number(norm(r["question"])),
            "options": opts,
            "correctAnswer": r["answer"].strip().upper(),
            "explanation": " ".join(parts),
            "task_id": r["task_id"],
        })

    print(f"  accepted: {len(accepted)}   refused: {len(refused)}")
    for reason, n in collections.Counter(
            x["reason"].split("(")[0].split(" of ")[0].strip()
            for x in refused).most_common():
        print(f"    {n:4d}  {reason}")

    by_year = collections.Counter(a["year"] for a in accepted)
    print("  by year:", dict(sorted(by_year.items(), reverse=True)))

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "promotion_ocr_refused.json"), "w",
              encoding="utf-8") as fh:
        json.dump(refused, fh, ensure_ascii=False, indent=1)

    if args.dry_run:
        print("\ndry run: no bank files written")
        return

    # ---- fold into the year banks -------------------------------------
    banks = {}
    for path in glob.glob(os.path.join(DATA, "promotion-*.json")):
        with open(path, encoding="utf-8") as fh:
            banks[os.path.basename(path)] = json.load(fh)

    # Map a year onto the bank file that already holds it.
    year_to_file = {}
    for name, qs in banks.items():
        for q in qs:
            year_to_file.setdefault(q["year"], name)

    added = collections.Counter()
    unplaced = []
    for a in accepted:
        name = year_to_file.get(a["year"])
        if not name:
            unplaced.append(a)
            continue
        source = banks[name][0]["source"] if banks[name] else name[:-5]
        existing = {norm(q["question"]).lower() for q in banks[name]}
        if norm(a["question"]).lower() in existing:
            refused.append({"task_id": a["task_id"], "type": "question",
                            "reason": "already present in the bank from the text layer",
                            "notes": ""})
            continue
        banks[name].append({
            "id": 0,
            "source": source,
            "question": a["question"],
            "options": a["options"],
            "correctAnswer": a["correctAnswer"],
            "explanation": a["explanation"],
            "year": a["year"],
            "subspecialty": a["subspecialty"],
            "pdfPage": a["pdfPage"],
            "imageUrl": a["imageUrl"],
            "ocr": True,
        })
        added[name] += 1

    for name, qs in banks.items():
        qs.sort(key=lambda q: (q["year"], q["pdfPage"], q.get("ocr", False)))
        for i, q in enumerate(qs, 1):
            q["id"] = i
        with open(os.path.join(DATA, name), "w", encoding="utf-8") as fh:
            json.dump(qs, fh, ensure_ascii=False, indent=1)

    print("\n  added per bank:", dict(added))
    if unplaced:
        print(f"  {len(unplaced)} could not be placed in a bank "
              f"(years: {sorted({u['year'] for u in unplaced})})")

    # ---- refresh manifest counts --------------------------------------
    mpath = os.path.join(DATA, "manifest.json")
    with open(mpath, encoding="utf-8") as fh:
        manifest = json.load(fh)
    for s in manifest["questionSets"]:
        if s["file"] in banks:
            n = len(banks[s["file"]])
            s["description"] = re.sub(r"^\d+", str(n), s["description"])
            s["questionCount"] = n
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in banks.values())
    print(f"  Promotion total now {total} questions "
          f"({sum(added.values())} transcribed)")

    with open(os.path.join(REPORT_DIR, "promotion_ocr_refused.json"), "w",
              encoding="utf-8") as fh:
        json.dump(refused, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
