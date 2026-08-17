#!/usr/bin/env python3
"""
Attach reviewer second opinions to the published banks, and build the separate
bank of reviewer-answered recalls.

Two inputs:

  scripts/review/review_result_*.json   -- a second opinion on every published
      question: an independently-reached answer, whether it matches the source's
      key, and a teaching explanation.  A disagreement is shown to the reader in
      its own colour; it never overwrites `correctAnswer`.  The exam's key is
      what the exam will mark, and a reviewer is not the exam.

  scripts/unkeyed/unkeyed_result_*.json -- answers for recalls the source left
      unkeyed.  These ship as their own bank, labelled reviewer-answered, so the
      provenance of the key is never ambiguous.

Usage:  python scripts/merge_expert_review.py [--dry-run]
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
REVIEW_DIR = os.path.join(REPORT_DIR, "review")
UNKEYED_DIR = os.path.join(REPORT_DIR, "unkeyed")

UNKEYED_BANK = "promotion-unkeyed"
UNKEYED_FILE = "promotion-unkeyed.json"
MIN_EXPLANATION = 40


def load_all(pattern):
    rows = []
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, encoding="utf-8") as fh:
                rows.extend(json.load(fh))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  !! {os.path.basename(path)}: {exc}")
    return rows


def clean(text):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    # Reviewers occasionally slip into markdown despite being asked not to.
    text = re.sub(r"^[#>\-\*\s]+", "", text)
    return text.replace("**", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # ---------------------------------------------------------------- reviews
    reviews = {r["task_id"]: r for r in load_all(
        os.path.join(REVIEW_DIR, "review_result_*.json")) if r.get("task_id")}
    print(f"second opinions loaded: {len(reviews)}")

    banks = {}
    for path in sorted(glob.glob(os.path.join(DATA, "promotion-*.json"))):
        if os.path.basename(path) == UNKEYED_FILE:
            continue
        banks[path] = json.load(open(path, encoding="utf-8"))

    attached = disagreements = skipped = 0
    conf = collections.Counter()
    for path, data in banks.items():
        for q in data:
            r = reviews.get(f"{q['source']}#{q['id']}")
            if not r:
                q.pop("review", None)
                continue
            answer = (r.get("answer") or "").strip().upper()
            explanation = clean(r.get("explanation"))
            if answer not in q["options"] or len(explanation) < MIN_EXPLANATION:
                # An answer outside the option set, or a stub explanation, is a
                # broken review rather than a finding.
                skipped += 1
                q.pop("review", None)
                continue
            agrees = answer == q["correctAnswer"]
            entry = {
                "answer": answer,
                "agrees": agrees,
                "confidence": (r.get("confidence") or "medium").lower(),
                "explanation": explanation,
            }
            concern = clean(r.get("concern"))
            if concern:
                entry["concern"] = concern
            q["review"] = entry
            attached += 1
            conf[entry["confidence"]] += 1
            disagreements += (not agrees)

    print(f"  attached: {attached}   disagreeing with the source key: {disagreements}"
          f"   rejected as malformed: {skipped}")
    print(f"  reviewer confidence: {dict(conf)}")

    # ---------------------------------------------------------------- unkeyed
    answers = {r["task_id"]: r for r in load_all(
        os.path.join(UNKEYED_DIR, "unkeyed_result_*.json")) if r.get("task_id")}
    sources = {}
    for path in sorted(glob.glob(os.path.join(UNKEYED_DIR, "unkeyed_batch_*.json"))):
        for t in json.load(open(path, encoding="utf-8")):
            sources[t["task_id"]] = t

    unkeyed, dropped = [], collections.Counter()
    for task_id, src in sources.items():
        r = answers.get(task_id)
        if not r:
            dropped["never reviewed"] += 1
            continue
        if not r.get("usable", True):
            dropped["reviewer judged it unusable"] += 1
            continue
        answer = (r.get("answer") or "").strip().upper()
        explanation = clean(r.get("explanation"))
        if answer not in src["options"]:
            dropped["answer outside the options"] += 1
            continue
        if len(explanation) < MIN_EXPLANATION:
            dropped["explanation too thin"] += 1
            continue
        item = {
            "id": 0,
            "source": UNKEYED_BANK,
            "question": src["question"],
            "options": src["options"],
            "correctAnswer": answer,
            "explanation": explanation,
            "year": src.get("year"),
            "subspecialty": "Miscellaneous",
            "pdfPage": src.get("pdfPage"),
            "reviewerAnswered": True,
            "reviewConfidence": (r.get("confidence") or "medium").lower(),
        }
        if src.get("sourceHint", "").strip():
            item["sourceHint"] = src["sourceHint"].strip()
        if clean(r.get("concern")):
            item["reviewConcern"] = clean(r.get("concern"))
        # Only attach a figure that is actually on disk: the parser prunes
        # anything nothing references, and a dangling path would render as a
        # broken image in the app.
        present = [u for u in (src.get("images") or [])
                   if os.path.exists(os.path.join(ROOT, "public",
                                                  u.lstrip("/").replace("/", os.sep)))]
        if present:
            item["imageUrl"] = present[0]
            if len(present) > 1:
                item["imageUrls"] = present[1:]
        unkeyed.append(item)

    unkeyed.sort(key=lambda q: (q["year"] or "", q["pdfPage"] or 0))
    for i, q in enumerate(unkeyed, 1):
        q["id"] = i

    print(f"\nunkeyed recalls: {len(sources)} candidates -> {len(unkeyed)} shippable")
    for why, n in dropped.most_common():
        print(f"    {n:4d}  {why}")
    print("  reviewer confidence:",
          dict(collections.Counter(q["reviewConfidence"] for q in unkeyed)))

    if args.dry_run:
        print("\ndry run: nothing written")
        return

    for path, data in banks.items():
        json.dump(data, io.open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    if unkeyed:
        json.dump(unkeyed, io.open(os.path.join(DATA, UNKEYED_FILE), "w",
                                   encoding="utf-8"), ensure_ascii=False, indent=1)
        register_bank(len(unkeyed))
    print(f"\n  written: {len(banks)} banks updated, "
          f"{UNKEYED_FILE} with {len(unkeyed)} questions")


def register_bank(count):
    """Add or refresh the reviewer-answered bank in the manifest."""
    path = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(path, encoding="utf-8"))
    sets = [s for s in manifest["questionSets"] if s["id"] != UNKEYED_BANK]
    sets.append({
        "id": UNKEYED_BANK,
        "name": "Promotion - Unkeyed (reviewer-answered)",
        "description": (f"{count} recalls the source document never answered. "
                        "Keys here come from a reviewer, not from the exam - "
                        "read them as study notes, not as verified answers."),
        "file": UNKEYED_FILE,
        "questionCount": count,
        "category": "promotion",
        "source": "Promotion",
    })
    manifest["questionSets"] = sets
    json.dump(manifest, io.open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
