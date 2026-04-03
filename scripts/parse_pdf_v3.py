#!/usr/bin/env python3
"""
Parse Pediatric BCSC Self Assessment PDF — V3 (anchor-based approach).

Strategy:
1. Find ALL "LETTER.\\npct%" anchors in the text (these never appear in noise)
2. Group consecutive anchors into option sets (A,B,C,D)
3. For each anchor, look BACKWARD to find the option text (avoiding explanation contamination)
4. Find question headers separately
5. Match option sets to questions by sequential order
"""

import json
import re
import sys
import os
import glob


def extract_text_from_pdf(pdf_path: str) -> str:
    import fitz
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


NOISE_SET = {
    '!', '\u201c', '\u201d', '"', '#', '$', '%', 'OFF', 'ON', 'Y',
    'Explanation & Notes', 'Discussion', 'BCSC Excerpt',
    'References', 'Notes', 'respondents', 'answered',
    'correctly.', '\ufeff', 'Expand', 'all', 'Filter by',
    'All', 'Questions', 'view', '50 per page', 'PEDIA Y',
}


def is_noise(line: str) -> bool:
    if line in NOISE_SET:
        return True
    if re.match(r'^\d+%\s*(of)?$', line):
        return True
    if re.match(r'^Exam History', line):
        return True
    if re.match(r'^Displaying questions', line):
        return True
    if re.match(r'^\d+ per page$', line):
        return True
    if re.match(r'^(?:[A-E]\.\s*\d+%\s*)+$', line):
        return True
    if re.match(r'^id=[a-f0-9]', line):
        return True
    if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}', line):
        return True
    return False


def is_question_header(line: str):
    return re.match(r'^(\d{1,3})\.[  \xa0]+(.+)', line)


# ── Step 1: Find question headers ──────────────────────────────────

def find_question_headers(lines):
    headers = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        m = is_question_header(line)
        if m:
            q_num = int(m.group(1))
            q_parts = [m.group(2).strip()]
            i += 1
            while i < n:
                sl = lines[i].strip()
                if not sl or is_noise(sl) or sl.startswith('(https://'):
                    break
                if is_question_header(sl):
                    break
                q_parts.append(sl)
                i += 1
            q_text = ' '.join(q_parts)
            q_text = re.sub(r'\s*[!\u201c\u201d"#$%]\s*', ' ', q_text)
            q_text = re.sub(r'\s+', ' ', q_text).strip()
            headers.append((i, q_num, q_text))
        else:
            i += 1
    return headers


# ── Step 2: Find all letter anchors ────────────────────────────────

def find_letter_anchors(lines):
    """
    Find all lines matching: LETTER. (alone) followed by pct% on next line.
    These are the definitive markers for answer options.
    Returns: list of (line_idx, letter, pct, is_correct)
    """
    anchors = []
    n = len(lines)
    for i in range(n - 1):
        line = lines[i].strip()
        m = re.match(r'^([A-E])\.\s*$', line)
        if not m:
            continue
        letter = m.group(1)

        # Next non-empty line should be pct%
        j = i + 1
        while j < n and not lines[j].strip():
            j += 1
        if j >= n:
            continue

        pct_line = lines[j].strip()
        pm = re.match(r'^(\d+)%\s*(Correct|Your)?', pct_line)
        if not pm:
            continue

        pct = int(pm.group(1))
        is_correct = pm.group(2) == 'Correct'

        # Check for "Answer" on line after pct
        answer_line = j + 1
        if answer_line < n and lines[answer_line].strip() == 'Answer':
            pass  # confirmed

        anchors.append((i, letter, pct, is_correct))

    return anchors


# ── Step 3: Group anchors into option sets ─────────────────────────

def group_into_option_sets(anchors):
    """
    Group consecutive anchors into sets. A new set starts when:
    - We see 'A' after a gap (>20 lines from previous anchor)
    - We see 'A' and the previous anchor was 'D' or 'E'
    """
    if not anchors:
        return []

    sets = []
    current_set = [anchors[0]]

    for k in range(1, len(anchors)):
        prev_line, prev_letter, _, _ = anchors[k - 1]
        curr_line, curr_letter, _, _ = anchors[k]

        # New set if: letter goes back to A/B with a gap, or large line gap
        gap = curr_line - prev_line
        if curr_letter <= prev_letter and gap > 3:
            # Likely a new option set
            sets.append(current_set)
            current_set = [anchors[k]]
        elif gap > 40:
            # Large gap means new block
            sets.append(current_set)
            current_set = [anchors[k]]
        else:
            current_set.append(anchors[k])

    if current_set:
        sets.append(current_set)

    return sets


# ── Step 4: Extract option text by looking BACKWARD from anchors ───

def extract_option_text(lines, anchor_line, prev_boundary):
    """
    Look backward from anchor_line to collect option text.
    prev_boundary = line index we must not go before (previous anchor's pct line + 2,
    or the start of the option set region).

    Option text is on the line(s) immediately before the letter marker,
    skipping noise/empty lines.
    """
    parts = []
    i = anchor_line - 1

    while i >= prev_boundary:
        line = lines[i].strip()

        # Skip empty
        if not line:
            i -= 1
            continue

        # Stop at noise (stats bars, UI elements)
        if is_noise(line):
            break

        # Stop at URL lines
        if line.startswith('(https://') or re.match(r'^id=[a-f0-9]', line):
            break
        if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}', line):
            break

        # Stop at question headers
        if is_question_header(line):
            break

        # Stop at "Answer" line (belongs to previous option)
        if line == 'Answer':
            break

        # Stop at pct% line (belongs to previous option)
        if re.match(r'^\d+%', line):
            break

        # Stop at letter marker (previous option)
        if re.match(r'^[A-E]\.\s*$', line):
            break

        parts.insert(0, line)
        i -= 1

    text = ' '.join(parts)
    text = re.sub(r'[\ue000-\uf8ff]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def build_option_set_data(lines, option_set):
    """
    Build options dict, correct answer, and stats from an option set.
    Also collects explanation text after the last option.
    """
    options = {}
    correct_answer = None
    stats = {}

    for idx, (anchor_line, letter, pct, is_correct) in enumerate(option_set):
        stats[letter] = pct
        if is_correct:
            correct_answer = letter

        # Determine backward boundary: line after previous anchor's "Answer" line
        if idx == 0:
            # For first option (A), look back at most 10 lines
            prev_boundary = max(0, anchor_line - 10)
        else:
            prev_anchor_line = option_set[idx - 1][0]
            # Previous anchor's pct line is anchor_line+1, "Answer" might be +2
            prev_boundary = prev_anchor_line + 2
            # Skip past "Answer" line if present
            if prev_boundary < len(lines) and lines[prev_boundary].strip() == 'Answer':
                prev_boundary += 1

        opt_text = extract_option_text(lines, anchor_line, prev_boundary)
        if opt_text:
            options[letter] = opt_text

    # Collect explanation after last anchor
    last_anchor = option_set[-1]
    expl_start = last_anchor[0] + 2  # skip letter + pct lines
    if expl_start < len(lines) and lines[expl_start].strip() == 'Answer':
        expl_start += 1

    expl_parts = []
    for k in range(expl_start, min(expl_start + 80, len(lines))):
        sl = lines[k].strip()
        if not sl:
            continue
        if is_noise(sl) or sl.startswith('(https://'):
            continue
        if is_question_header(sl):
            break
        # Stop if we hit another option block (A. marker followed by pct)
        if re.match(r'^[A-E]\.\s*$', sl):
            if k + 1 < len(lines) and re.match(r'^\d+%', lines[k + 1].strip()):
                break
        expl_parts.append(sl)

    explanation = ' '.join(expl_parts)
    explanation = re.sub(r'\s+', ' ', explanation).strip()

    return options, correct_answer, dict(sorted(stats.items())), explanation


# ── Step 5: Match and build questions ──────────────────────────────

def build_questions(headers, option_sets_data, lines, source_id):
    """Match option sets to questions by sequential order."""
    headers_sorted = sorted(headers, key=lambda h: h[1])  # sort by q_num
    option_sets_sorted = option_sets_data  # already in text order

    questions = []
    for idx, (_, q_num, q_text) in enumerate(headers_sorted):
        q = {
            "id": q_num,
            "source": source_id,
            "question": q_text,
            "options": {},
            "correctAnswer": None,
            "explanation": "",
            "respondentStats": None,
            "imageUrl": None,
        }

        if idx < len(option_sets_sorted):
            opts, correct, stats, expl = option_sets_sorted[idx]
            q["options"] = dict(sorted(opts.items()))
            q["correctAnswer"] = correct
            q["respondentStats"] = stats if stats else None
            q["explanation"] = expl

        if len(q["options"]) >= 2 and len(q["question"]) > 10:
            questions.append(q)

    return questions


# ── Main ────────────────────────────────────────────────────────────

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    pdf_path = None
    for pattern in ["Pediatric*BCSC*.pdf", "Pediatric*.pdf"]:
        matches = glob.glob(os.path.join(project_dir, pattern))
        if matches:
            pdf_path = matches[0]
            break

    if not pdf_path:
        print("PDF not found!")
        sys.exit(1)

    print(f"Extracting: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    lines = text.split('\n')
    print(f"  {len(text)} chars, {len(lines)} lines")

    source_id = "pediatric-bcsc"

    print("Step 1: Finding question headers...")
    headers = find_question_headers(lines)
    print(f"  Found {len(headers)} headers")

    # Deduplicate headers by q_num (keep first occurrence)
    seen_nums = set()
    unique_headers = []
    for h in headers:
        if h[1] not in seen_nums:
            seen_nums.add(h[1])
            unique_headers.append(h)
    headers = unique_headers
    print(f"  Unique: {len(headers)} headers")

    print("Step 2: Finding letter anchors...")
    anchors = find_letter_anchors(lines)
    print(f"  Found {len(anchors)} anchors")

    print("Step 3: Grouping into option sets...")
    option_sets = group_into_option_sets(anchors)
    print(f"  Found {len(option_sets)} option sets")

    # Filter: keep only sets with 2+ options
    option_sets = [s for s in option_sets if len(s) >= 2]
    print(f"  Valid sets (2+ options): {len(option_sets)}")

    print("Step 4: Extracting option text...")
    option_sets_data = []
    for oset in option_sets:
        data = build_option_set_data(lines, oset)
        option_sets_data.append(data)

    print("Step 5: Matching to questions...")
    questions = build_questions(headers, option_sets_data, lines, source_id)

    # Deduplicate
    seen = set()
    unique = []
    for q in questions:
        if q["id"] not in seen:
            seen.add(q["id"])
            unique.append(q)
    questions = sorted(unique, key=lambda q: q["id"])

    print(f"\n=== RESULTS ===")
    print(f"Total questions: {len(questions)}")
    with_correct = sum(1 for q in questions if q["correctAnswer"])
    with_expl = sum(1 for q in questions if q["explanation"])
    with_4opts = sum(1 for q in questions if len(q["options"]) >= 4)
    print(f"  With correct answer: {with_correct}")
    print(f"  With explanation: {with_expl}")
    print(f"  With 4+ options: {with_4opts}")

    # Verify key questions
    for qid in [1, 2, 3, 4, 5, 7, 8, 9, 17, 50, 100, 200, 300, 400, 486]:
        q = next((q for q in questions if q['id'] == qid), None)
        if q:
            print(f"\n  Q{q['id']}: {q['question'][:70]}")
            for k, v in sorted(q['options'].items()):
                marker = " <<<" if k == q['correctAnswer'] else ""
                print(f"    {k}: {v[:60]}{marker}")

    missing = sorted(set(range(1, 487)) - {q["id"] for q in questions})
    print(f"\nMissing ({len(missing)}): {missing[:30]}{'...' if len(missing) > 30 else ''}")

    # Output
    output_dir = os.path.join(project_dir, "public", "data")
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, f"{source_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    print(f"\nJSON: {json_path}")

    manifest = {
        "questionSets": [{
            "id": source_id,
            "name": "Pediatric BCSC Self Assessment",
            "description": f"{len(questions)} questions on Pediatric Ophthalmology",
            "file": f"{source_id}.json",
            "questionCount": len(questions),
        }]
    }
    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("Manifest written.")


if __name__ == "__main__":
    main()
