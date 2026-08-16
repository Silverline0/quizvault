#!/usr/bin/env python3
"""
Fix 49 contaminated answer options across 7 JSON quiz files.

Contamination pattern (BCSC files):
  The interleaved PDF layout caused the NEXT question's text to get concatenated
  into the LAST option of the CURRENT question during parsing. The structure is:
    [leaked_next_question_text] ! " # [REAL_option_text]
  where ! " # (or ! % # or ! & #) is a PDF UI artifact marker.
  The REAL option text is AFTER the marker.

Contamination pattern (cornea-oq):
  Q95 opt D: real option + "Answer: " + explanation text
  Q269 opt D: real option + "A; C " + answer key + explanation text
"""

import json
import re
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "public", "data")

# ── Detection ──────────────────────────────────────────────────────────────────

# PDF UI artifact marker: ! followed by one of " % & # then #
MARKER_RE = re.compile(r'!\s*["%&#]\s*#')

def is_bcsc_contaminated(text):
    """Detect BCSC-style contamination: leaked next-question text + marker + real option."""
    return bool(MARKER_RE.search(text))

def is_oq_answer_contaminated(text):
    """Detect OphthoQ-style contamination: real option + Answer: + explanation."""
    return bool(re.search(r'\bAnswer:\s', text)) and len(text) > 100

def is_oq_answerkey_contaminated(text):
    """Detect OphthoQ-style contamination: real option + 'A; C ...' answer key."""
    return bool(re.match(r'^.{5,80}\s+[A-D];\s*[A-D]\s', text))


# ── Extraction ─────────────────────────────────────────────────────────────────

def fix_bcsc_option(text):
    """Extract real option text from BCSC contaminated option.
    
    Pattern: [leaked_text] ! " # [real_option]
    Real option is everything AFTER the marker.
    """
    m = MARKER_RE.search(text)
    if not m:
        return text
    after = text[m.end():].strip()
    # Clean up any trailing whitespace or artifacts
    after = after.rstrip()
    return after

def fix_oq_answer_option(text):
    """Extract real option from OphthoQ option contaminated with Answer text.
    
    Pattern: [real_option] Answer: [explanation...]
    Real option is everything BEFORE 'Answer:'.
    """
    idx = text.find("Answer:")
    if idx < 0:
        idx = text.find("Answer :")
    if idx < 0:
        return text
    before = text[:idx].strip()
    return before

def fix_oq_answerkey_option(text):
    """Extract real option from OphthoQ option contaminated with answer key.
    
    Pattern: [real_option] A; C [explanation...]
    Real option is everything BEFORE the answer key pattern.
    """
    m = re.search(r'\s+[A-D];\s*[A-D]\s', text)
    if not m:
        return text
    before = text[:m.start()].strip()
    return before


# ── Main processing ────────────────────────────────────────────────────────────

def process_file(json_path, file_type="bcsc"):
    """Process a single JSON file and fix contaminated options.
    
    Returns list of (question_index, letter, old_text, new_text) tuples.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    questions = data if isinstance(data, list) else data.get("questions", [])
    fixes = []
    
    for qi, q in enumerate(questions):
        opts = q.get("options", {})
        for letter, text in opts.items():
            new_text = None
            
            if file_type == "bcsc":
                if is_bcsc_contaminated(text):
                    new_text = fix_bcsc_option(text)
            elif file_type == "oq":
                if is_oq_answer_contaminated(text):
                    new_text = fix_oq_answer_option(text)
                elif is_oq_answerkey_contaminated(text):
                    new_text = fix_oq_answerkey_option(text)
            
            if new_text is not None and new_text != text:
                fixes.append((qi, letter, text, new_text))
                opts[letter] = new_text
    
    return data, fixes


# ── Manual PDF-verified corrections ─────────────────────────────────────��──────
# These options had the real text completely replaced by leaked next-question text
# (no marker present), so the correct values were extracted manually from the PDFs.

MANUAL_FIXES = {
    "oculoplastics-bcsc.json": {
        (81, "B"): "ipsilateral eyebrow depression",
        (157, "B"): "20 mm of skin between the inferior border of the brow and the upper eyelid margin",
        (236, "C"): "1 mm ptosis, poor levator function, persistence of ptosis with instillation of a drop of 2.5% phenylephrine hydrochloride",
        (364, "C"): "It is located at the distal portion of the nasolacrimal duct.",
        (400, "D"): "dacryoadenitis",
    },
    "pediatric-bcsc.json": {
        (173, "D"): "IOL implantation in infants aged 1 to 6 months is associated with a higher rate of adverse events requiring further surgery but overall better grating acuity at 1 year.",
        (377, "D"): "recession of right lateral rectus, resection of right medial rectus, recession of left medial rectus, resection of left lateral rectus",
    },
    "retina-bcsc.json": {
        (211, "D"): "subretinal hard exudate",
    },
    "glaucoma-bcsc.json": {
        (173, "B"): "diode laser cyclophotocoagulation",
    },
    "cornea-oq.json": {
        (237, "D"): "serovars M2",
    },
}


# ── File definitions ───────────────────────────────────────────────────────────

FILES = [
    # (json filename, type)
    ("oculoplastics-bcsc.json", "bcsc"),
    ("pediatric-bcsc.json",    "bcsc"),
    ("retina-bcsc.json",       "bcsc"),
    ("glaucoma-bcsc.json",     "bcsc"),
    ("cornea-bcsc.json",       "bcsc"),
    ("cornea-oq.json",         "oq"),
    # neuro-oq.json has 0 real contaminations (long options are legitimate scenarios)
]

def apply_manual_fixes(data, fname):
    """Apply manually verified fixes from PDF lookup."""
    manual = MANUAL_FIXES.get(fname, {})
    fixes = []
    questions = data if isinstance(data, list) else data.get("questions", [])
    for (qi, letter), new_text in manual.items():
        if qi < len(questions):
            old_text = questions[qi]["options"].get(letter, "")
            if old_text != new_text:
                fixes.append((qi, letter, old_text, new_text))
                questions[qi]["options"][letter] = new_text
    return data, fixes


def main():
    total_fixes = 0
    all_examples = []  # Collect up to 5 before/after examples
    
    for fname, ftype in FILES:
        json_path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(json_path):
            print(f"WARNING: {json_path} not found, skipping")
            continue
        
        # Phase 1: auto-detect and fix marker-based contamination
        data, fixes = process_file(json_path, ftype)
        
        # Phase 2: apply manual PDF-verified fixes for marker-less contamination
        data, manual_fixes = apply_manual_fixes(data, fname)
        fixes.extend(manual_fixes)
        
        if fixes:
            # Write fixed data back
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            total_fixes += len(fixes)
            print(f"{fname}: fixed {len(fixes)} contaminated options")
            
            for qi, letter, old_text, new_text in fixes:
                print(f"  Q{qi} opt {letter}: \"{old_text[:80]}...\"")
                print(f"       -> \"{new_text}\"")
                if len(all_examples) < 5:
                    all_examples.append((fname, qi, letter, old_text, new_text))
        else:
            print(f"{fname}: no contamination found")
    
    print(f"\n{'='*70}")
    print(f"TOTAL: {total_fixes} contaminated options fixed across {len(FILES)} files")
    print(f"{'='*70}")
    
    if all_examples:
        print(f"\n{'='*70}")
        print("BEFORE/AFTER EXAMPLES (first 5)")
        print(f"{'='*70}")
        for i, (fname, qi, letter, old_text, new_text) in enumerate(all_examples, 1):
            print(f"\n--- Example {i}: {fname} Q{qi} option {letter} ---")
            print(f"BEFORE ({len(old_text)} chars):")
            print(f"  {old_text}")
            print(f"AFTER ({len(new_text)} chars):")
            print(f"  {new_text}")

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
