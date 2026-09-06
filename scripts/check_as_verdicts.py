#!/usr/bin/env python3
"""
Validate the reviewer's verdicts on the Anterior Segment quiz.

A review is only worth having if it cannot quietly skip anything, so the file
is checked against the bank rather than read on trust: every question present
exactly once, every verdict from the agreed vocabulary, every non-"correct"
verdict carrying real reasoning, and every proposed answer actually one of that
question's options and different from the marked key.

A file that fails here is sent back rather than merged.

    python scripts/check_as_verdicts.py
"""

import collections
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "public", "data", "anterior-segment-quiz.json")
VERDICTS = os.path.join(ROOT, "scripts", "audit", "as_quiz_verdicts.json")

ALLOWED = {"correct", "wrong-answer", "explanation-contradicts",
           "ambiguous", "unanswerable"}
MIN_REASON = 80


def main():
    bank = {q["id"]: q for q in json.load(open(BANK, encoding="utf-8"))}
    if not os.path.exists(VERDICTS):
        sys.exit(f"no verdict file at {VERDICTS}")
    rows = json.load(open(VERDICTS, encoding="utf-8"))
    if not isinstance(rows, list):
        sys.exit("the verdict file must be a JSON list")

    problems, seen = [], {}
    for row in rows:
        qid = row.get("id")
        if qid not in bank:
            problems.append(f"id {qid} is not in this bank")
            continue
        if qid in seen:
            problems.append(f"id {qid} appears twice")
        seen[qid] = row

        verdict = row.get("verdict")
        if verdict not in ALLOWED:
            problems.append(f"id {qid}: verdict {verdict!r} is not one of the agreed set")
            continue
        reason = (row.get("reason") or "").strip()
        if verdict != "correct" and len(reason) < MIN_REASON:
            problems.append(f"id {qid}: {verdict} needs at least {MIN_REASON} "
                            f"characters of reasoning, got {len(reason)}")
        proposed = row.get("proposedAnswer")
        if verdict == "wrong-answer":
            if proposed not in bank[qid]["options"]:
                problems.append(f"id {qid}: proposed answer {proposed!r} is not one "
                                f"of this question's options")
            elif proposed == bank[qid]["correctAnswer"]:
                problems.append(f"id {qid}: proposed answer equals the marked key")
        elif proposed:
            problems.append(f"id {qid}: {verdict} should not propose an answer")

    missing = sorted(set(bank) - set(seen))
    if missing:
        problems.append(f"{len(missing)} question(s) not reviewed: {missing[:15]}")

    counts = collections.Counter(r.get("verdict") for r in seen.values())
    print(f"{len(seen)}/{len(bank)} reviewed  {dict(counts)}")
    if problems:
        print(f"\nFAIL — {len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1

    print("\nok — the file is complete and internally consistent")
    flagged = [(qid, r) for qid, r in sorted(seen.items())
               if r["verdict"] != "correct"]
    print(f"  {len(flagged)} question(s) flagged:")
    for qid, r in flagged:
        marked = bank[qid]["correctAnswer"]
        prop = r.get("proposedAnswer")
        print(f"    #{qid} {r['verdict']}: marked {marked}"
              + (f", proposed {prop}" if prop else "")
              + f"  — {bank[qid]['question'][:58]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
