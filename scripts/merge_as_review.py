#!/usr/bin/env python3
"""
Attach the independent review to the Anterior Segment quiz.

The reviewer's verdicts are recorded as a second opinion, never as a new key.
That is the rule the bank already runs on: the exam's key is what the exam
marks, and a reviewer is not the exam.  A reader gets both, told apart, and
decides.

Only the questions the reviewer did not pass are given a review block; marking
all 45 would bury the three that matter under forty-two that say "yes".

    python scripts/merge_as_review.py --dry-run
    python scripts/merge_as_review.py
"""

import argparse
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "public", "data", "anterior-segment-quiz.json")
VERDICTS = os.path.join(ROOT, "scripts", "audit", "as_quiz_verdicts.json")

# The reviewer's own reasoning, written into the shape the panel renders. The
# "answer" for a question no option answers is stated in words rather than as a
# letter, because there is no letter that would be true.
REVIEWS = {
    24: {
        "answer": "neural crest + neuroectoderm",
        "agrees": False,
        "answerMissing": True,
        "confidence": "high",
        "explanation": (
            "No option is correct as written. The iris stroma derives from neural "
            "crest mesenchyme, while the iris pigment epithelium and both the "
            "sphincter and dilator muscles derive from neuroectoderm of the optic "
            "cup. Surface ectoderm contributes the lens and the corneal epithelium "
            "and nothing to the iris, so the marked option C pairs a right "
            "component with a wrong one."
        ),
        "concern": (
            "The author reached the same conclusion and kept C anyway as the "
            "least wrong of the four on offer, so this is a defect in the options "
            "rather than a dispute about the embryology."
        ),
    },
    33: {
        "answer": "D",
        "agrees": False,
        "confidence": "high",
        "explanation": (
            "Topical corticosteroids are the exception, not tight contact lenses. "
            "For hyperopic overcorrection after PRK the steroid is what maintains "
            "the hyperopia by suppressing regression, so management is to taper it "
            "off rather than to give it. Tight-fitting soft lenses steepen the "
            "cornea toward a myopic shift, topical NSAIDs encourage regression, and "
            "hyperopic PRK retreatment is the surgical option -- all three are "
            "treatments, which leaves D as the one that is not."
        ),
        "concern": (
            "The explanation calls a tight lens flat-fitting and says it flattens "
            "the cornea, which is the wrong way round: a tight lens steepens it."
        ),
    },
    34: {
        "answer": "B",
        "agrees": False,
        "confidence": "medium",
        "explanation": (
            "Two of the pairs are mismatched rather than one. Amikacin against "
            "Propionibacterium acnes is wrong, as an aminoglycoside has no useful "
            "activity against that anaerobe. But Pseudomonas aeruginosa is also "
            "intrinsically resistant to chloramphenicol, so option B is mismatched "
            "on the same reading and the question has two defensible answers."
        ),
        "concern": (
            "The marked answer E is defensible; the problem is that B is equally "
            "so, and the explanation never addresses it."
        ),
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verdicts = {v["id"]: v for v in json.load(open(VERDICTS, encoding="utf-8"))}
    flagged = {qid for qid, v in verdicts.items() if v["verdict"] != "correct"}
    if flagged != set(REVIEWS):
        sys.exit(f"the reviewer flagged {sorted(flagged)} but this file writes "
                 f"{sorted(REVIEWS)} -- reconcile before merging")

    bank = json.load(open(BANK, encoding="utf-8"))
    touched = 0
    for q in bank:
        review = REVIEWS.get(q["id"])
        if not review:
            continue
        # A reviewer that lands on the marked letter is agreeing, whatever it
        # says; guard against writing a block that contradicts itself.
        if review["answer"] == q["correctAnswer"] and not review["agrees"]:
            sys.exit(f"#{q['id']}: review says it disagrees but names the marked key")
        q["review"] = review
        q["reviewedBy"] = "Fable 5.1, independent pass"
        touched += 1
        print(f"  #{q['id']}: marked {q['correctAnswer']}, reviewer says "
              f"{review['answer']} ({verdicts[q['id']]['verdict']})")

    if not args.dry_run:
        json.dump(bank, io.open(BANK, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"{touched} question(s) given a second opinion"
          + ("  (dry run, nothing written)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
