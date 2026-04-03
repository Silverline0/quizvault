#!/usr/bin/env python3
"""
Post-processing script for all parsed JSON files.
Fixes issues found by 30 Haiku verification agents:

1. BCSC null correctAnswers → infer from highest respondent stat %
2. OphthoQ null correctAnswers → detect letter_explanation pattern
3. Explanation garbage → strip UUID/timestamp/URL patterns
4. Long options with explanation contamination → split overflow to explanation
5. Clean up truncated text artifacts
"""

import json
import re
import os
import glob


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Fix 1: Infer null correctAnswer from respondent stats ──────────

def fix_null_answers_from_stats(questions):
    """For BCSC questions with respondentStats, pick the highest % as correct."""
    fixed = 0
    for q in questions:
        if q.get("correctAnswer") is not None:
            continue
        stats = q.get("respondentStats")
        if not stats:
            continue
        # Pick the letter with the highest percentage
        best_letter = max(stats, key=lambda k: stats[k])
        if best_letter in q.get("options", {}):
            q["correctAnswer"] = best_letter
            fixed += 1
    return fixed


# ── Fix 2: Detect letter_explanation pattern for OphthoQ ───────────

def fix_ophthoq_letter_explanation(questions):
    """
    For OphthoQ questions where the explanation starts with 'B. explanation text...',
    the parser may have:
    a) Captured the explanation as the last option → fix: remove it from options,
       set correctAnswer, move text to explanation
    b) Left correctAnswer null → fix: check if any option text is suspiciously long
       and looks like an explanation
    """
    fixed = 0
    for q in questions:
        options = q.get("options", {})
        if len(options) < 2:
            continue

        # Check if any option is suspiciously long (>200 chars) and looks like explanation
        for letter in sorted(options.keys()):
            text = options[letter]
            if len(text) > 200:
                # This is likely explanation text captured as an option
                # Move it to explanation and set this letter as correct answer
                if not q.get("correctAnswer"):
                    q["correctAnswer"] = letter
                q["explanation"] = text + " " + q.get("explanation", "")
                q["explanation"] = re.sub(r'\s+', ' ', q["explanation"]).strip()
                # Replace the option with just the first sentence or phrase
                # Try to find the actual option text (first phrase before explanation)
                first_sentence = re.split(r'(?<=[.!])\s+', text)
                if first_sentence and len(first_sentence[0]) < 150:
                    options[letter] = first_sentence[0]
                else:
                    # Take first ~80 chars up to a word boundary
                    truncated = text[:80].rsplit(' ', 1)[0]
                    options[letter] = truncated
                fixed += 1

        # If still no correct answer but explanation starts with "LETTER. "
        if not q.get("correctAnswer") and q.get("explanation"):
            expl = q["explanation"]
            m = re.match(r'^([A-E])\.\s+', expl)
            if m and m.group(1) in options:
                q["correctAnswer"] = m.group(1)
                q["explanation"] = re.sub(r'^[A-E]\.\s*', '', expl)
                fixed += 1

    return fixed


# ── Fix 3: Clean explanation garbage ───────────────────────────────

def clean_explanations(questions):
    """Strip UUID fragments, timestamps, URLs, and page footers from explanations."""
    fixed = 0
    for q in questions:
        expl = q.get("explanation", "")
        if not expl:
            continue

        original = expl

        # Remove UUID fragments: xxxx-xxxx-xxxx-xxxx patterns
        expl = re.sub(r'[a-f0-9]{4,}-[a-f0-9]{4}[-a-f0-9]*', '', expl)
        # Remove &t=timestamp patterns
        expl = re.sub(r'&t=\d+', '', expl)
        # Remove orphaned URL fragments
        expl = re.sub(r'\(https?://[^\)]*\)', '', expl)
        expl = re.sub(r'https?://\S+', '', expl)
        # Remove AAO footer text
        expl = re.sub(r'Prev\s+\d+.*?American Academy of Ophthalmology\s*\d*', '', expl)
        # Remove "Explanation:" prefix
        expl = re.sub(r'^Explanation\s*:\s*', '', expl, flags=re.IGNORECASE)
        # Remove "High Yield: Yes/No"
        expl = re.sub(r'High\s*Yield\s*:\s*(Yes|No)\s*', '', expl, flags=re.IGNORECASE)
        # Remove "Correct Answer: X"
        expl = re.sub(r'Correct\s*Answer\s*:\s*[A-E]\s*', '', expl, flags=re.IGNORECASE)
        # Clean up leading/trailing punctuation and whitespace
        expl = re.sub(r'^[\s\)\-&=]+', '', expl)
        expl = re.sub(r'\s+', ' ', expl).strip()

        if expl != original:
            q["explanation"] = expl
            fixed += 1

    return fixed


# ── Fix 4: Cap overly long options ─────────────────────────────────

def cap_long_options(questions, max_len=300):
    """
    For options exceeding max_len chars that aren't legitimate long medical text,
    truncate at the last sentence boundary before max_len.
    """
    fixed = 0
    for q in questions:
        for letter in list(q.get("options", {}).keys()):
            text = q["options"][letter]
            if len(text) <= max_len:
                continue

            # Try to find a natural break point
            parts = re.split(r'(?<=[.!?])\s+', text)
            truncated = ""
            for part in parts:
                if len(truncated) + len(part) + 1 > max_len:
                    break
                truncated = (truncated + " " + part).strip()

            if truncated and len(truncated) > 10:
                # Move overflow to explanation
                overflow = text[len(truncated):].strip()
                if overflow:
                    q["explanation"] = overflow + " " + q.get("explanation", "")
                    q["explanation"] = re.sub(r'\s+', ' ', q["explanation"]).strip()
                q["options"][letter] = truncated
                fixed += 1
            else:
                # Just hard truncate at word boundary
                truncated = text[:max_len].rsplit(' ', 1)[0]
                q["options"][letter] = truncated
                fixed += 1

    return fixed


# ── Fix 5: Remove empty/useless options ────────────────────────────

def clean_empty_options(questions):
    """Remove options that are empty or just whitespace."""
    fixed = 0
    for q in questions:
        for letter in list(q.get("options", {}).keys()):
            text = q["options"][letter].strip()
            if not text or len(text) < 2:
                del q["options"][letter]
                fixed += 1
    return fixed


# ── Main ───────────────────────────────────────────────────────────

def main():
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "public", "data"
    )

    json_files = sorted(glob.glob(os.path.join(data_dir, "*.json")))
    json_files = [f for f in json_files if not os.path.basename(f).startswith('_')
                  and os.path.basename(f) != 'manifest.json']

    print("POST-PROCESSING ALL JSON FILES")
    print("=" * 60)

    total_stats = {
        "null_answers_fixed": 0,
        "explanations_cleaned": 0,
        "long_options_capped": 0,
        "empty_options_removed": 0,
        "ophthoq_answers_fixed": 0,
    }

    for json_path in json_files:
        filename = os.path.basename(json_path)
        questions = load_json(json_path)

        if not isinstance(questions, list):
            continue

        print(f"\n{filename}: {len(questions)} questions")

        is_bcsc = "bcsc" in filename
        is_oq = "oq" in filename

        # Apply fixes
        n1 = fix_null_answers_from_stats(questions) if is_bcsc else 0
        n2 = fix_ophthoq_letter_explanation(questions) if is_oq else 0
        n3 = clean_explanations(questions)
        n4 = cap_long_options(questions)
        n5 = clean_empty_options(questions)

        total_stats["null_answers_fixed"] += n1
        total_stats["ophthoq_answers_fixed"] += n2
        total_stats["explanations_cleaned"] += n3
        total_stats["long_options_capped"] += n4
        total_stats["empty_options_removed"] += n5

        if n1 + n2 + n3 + n4 + n5 > 0:
            print(f"  Fixed: {n1} null answers (stats), {n2} OQ answers, "
                  f"{n3} explanations, {n4} long opts, {n5} empty opts")
            save_json(json_path, questions)
        else:
            print(f"  No fixes needed")

        # Report remaining issues
        still_null = sum(1 for q in questions if not q.get("correctAnswer"))
        still_empty_expl = sum(1 for q in questions if not q.get("explanation"))
        still_long_opts = sum(1 for q in questions
                             for v in q.get("options", {}).values()
                             if len(v) > 300)
        if still_null or still_empty_expl or still_long_opts:
            print(f"  Remaining: {still_null} null answers, "
                  f"{still_empty_expl} empty explanations, "
                  f"{still_long_opts} long options")

    print(f"\n{'=' * 60}")
    print("TOTAL FIXES APPLIED:")
    for k, v in total_stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
