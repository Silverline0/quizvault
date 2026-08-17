#!/usr/bin/env python3
"""
Build the work list of questions that need a substitute reference image.

Two groups qualify:

  * figureConfidence "low" -- a figure is attached but was matched by position
    alone and the stem never names it; measurement put this shape behind every
    confirmed misplacement.
  * the stem explicitly asks for a picture and none is attached.

For each, the clinical subject is the question's own words -- researchers are
expected to find an openly-licensed image of THAT finding, never to infer what
the question "should" be showing.

Usage:  python scripts/build_figure_worklist.py [--batches N]
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
OUT_DIR = os.environ.get("FIGURE_DIR", os.path.join(REPORT_DIR, "figures"))

DEMANDS = re.compile(
    r"\b(photo(graph)?\s+(shown|above|attached)|pictured\s+above|exact\s+pict"
    r"|picture\s+(shown|above|attached|of)|image\s+(shown|above|showing)"
    r"|shown\s+(in\s+the\s+)?(photo|picture|image|figure)|see\s+(the\s+)?pic"
    r"|as\s+shown|attached\s+(picture|photo|image)"
    r"|exactly\s+this\s+(picture|photo|image)|this\s+exact\s+(picture|photo|image)"
    r"|same\s+(exact\s+)?(picture|photo|pic)\b)", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=5)
    args = ap.parse_args()

    tasks = []
    for path in sorted(glob.glob(os.path.join(DATA, "promotion-*.json"))):
        for q in json.load(open(path, encoding="utf-8")):
            has = bool(q.get("imageUrl"))
            conf = q.get("figureConfidence")
            wants = bool(DEMANDS.search(f"{q['question']} {q.get('explanation','')}"))
            if has and conf == "low":
                need = "doubtful"
            elif not has and wants:
                need = "missing"
            else:
                continue
            tasks.append({
                "task_id": f"{q['source']}#{q['id']}",
                "bank": q["source"],
                "id": q["id"],
                "pdfPage": q["pdfPage"],
                "subspecialty": q.get("subspecialty", ""),
                "need": need,
                "question": q["question"],
                "options": q["options"],
                "correctAnswer": q["correctAnswer"],
                "currentImage": q.get("imageUrl"),
            })

    os.makedirs(OUT_DIR, exist_ok=True)
    size = (len(tasks) + args.batches - 1) // args.batches
    for b in range(args.batches):
        chunk = tasks[b * size:(b + 1) * size]
        if not chunk:
            continue
        with open(os.path.join(OUT_DIR, f"fig_batch_{b + 1}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(chunk, fh, ensure_ascii=False, indent=1)
        print(f"  fig_batch_{b + 1}.json: {len(chunk)}")

    kinds = collections.Counter(t["need"] for t in tasks)
    print(f"\n{len(tasks)} questions need a reference image: {dict(kinds)}")
    print(f"written to {OUT_DIR}")


if __name__ == "__main__":
    main()
