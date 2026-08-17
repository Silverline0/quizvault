#!/usr/bin/env python3
"""
Build the work lists for expert review.

Two jobs come out of this:

  review/  -- every published question, for a second opinion.  A reviewer answers
              it independently, then says whether that matches the source's key.
              Disagreements are surfaced to the reader in a distinct colour; they
              are a second opinion, never an override.

  unkeyed/ -- recalls the source never supplied an answer for.  These were held
              out of the published banks rather than guessed at.  A reviewer
              supplies an answer so they can ship in a clearly separate bank.

Usage:
  python scripts/build_review_worklist.py [--per-batch 60] [--unkeyed-per-batch 42]
"""

import argparse
import collections
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "public", "data")
REPORT_DIR = os.environ.get("PROMO_REPORT", os.path.join(ROOT, "scripts"))
REVIEW_DIR = os.path.join(REPORT_DIR, "review")
UNKEYED_DIR = os.path.join(REPORT_DIR, "unkeyed")


def chunk(items, size, out_dir, prefix):
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, f"{prefix}_batch_*.json")):
        os.remove(old)
    n = 0
    for b in range((len(items) + size - 1) // size):
        part = items[b * size:(b + 1) * size]
        if not part:
            continue
        n += 1
        with open(os.path.join(out_dir, f"{prefix}_batch_{n}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(part, fh, ensure_ascii=False, indent=1)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-batch", type=int, default=60)
    ap.add_argument("--unkeyed-per-batch", type=int, default=42)
    args = ap.parse_args()

    # ---- published questions -------------------------------------------
    published = []
    for path in sorted(glob.glob(os.path.join(DATA, "promotion-*.json"))):
        for q in json.load(open(path, encoding="utf-8")):
            published.append({
                "task_id": f"{q['source']}#{q['id']}",
                "year": q.get("year"),
                "subspecialty": q.get("subspecialty"),
                "pdfPage": q.get("pdfPage"),
                "question": q["question"],
                "options": q["options"],
                "sourceAnswer": q["correctAnswer"],
                "sourceExplanation": (q.get("explanation") or "")[:900],
                "hasImage": bool(q.get("imageUrl")),
                "figureConfidence": q.get("figureConfidence"),
            })
    nb = chunk(published, args.per_batch, REVIEW_DIR, "review")
    print(f"review: {len(published)} questions -> {nb} batches in {REVIEW_DIR}")

    # ---- unkeyed recalls ------------------------------------------------
    with open(os.path.join(REPORT_DIR, "promotion_rejects.json"),
              encoding="utf-8") as fh:
        rejects = json.load(fh)
    unkeyed = []
    for i, r in enumerate(rejects, 1):
        if not r.get("looks_like_question"):
            continue
        opts = r.get("options") or {}
        if len(opts) < 2:
            continue
        unkeyed.append({
            "task_id": f"unkeyed#{i}",
            "year": r.get("year"),
            "pdfPage": r.get("page"),
            "question": r.get("stem", ""),
            "options": opts,
            # Whatever the compiler wrote where an answer should be -- often a
            # hedge like "Not sure, D?" that is evidence but not a key.
            "sourceHint": r.get("answer_raw", ""),
            "images": r.get("images") or [],
        })
    nu = chunk(unkeyed, args.unkeyed_per_batch, UNKEYED_DIR, "unkeyed")
    print(f"unkeyed: {len(unkeyed)} recalls -> {nu} batches in {UNKEYED_DIR}")
    print("  by year:", dict(sorted(
        collections.Counter(u["year"] for u in unkeyed).items(), reverse=True)))


if __name__ == "__main__":
    main()
