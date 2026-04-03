#!/usr/bin/env python3
"""
Parse the Pediatric BCSC Self Assessment PDF into structured JSON — V2.

Key insight: The PDF's two-column layout causes an interleaved pattern:
  Q_N header → Q_N question text → noise
  Q_N+1 header → Q_N+1 question text → noise/stats
  Q_N's OPTIONS appear here (after Q_N+1's header!)
  Q_N's explanation
  Q_N+1's options appear after Q_N+2's header, etc.

Strategy: Instead of slicing by question headers, we parse the entire
stream sequentially. We collect option blocks and assign them to the
PREVIOUS question that doesn't have options yet.
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


NOISE = {
    '!', '\u201c', '\u201d', '"', '#', '$', '%', 'OFF', 'ON', 'Y',
    'Explanation & Notes', 'Discussion', 'BCSC Excerpt',
    'References', 'Notes', 'respondents', 'answered',
    'correctly.', '\ufeff', 'Expand', 'all', 'Filter by',
    'All', 'Questions', 'view', '50 per page', 'PEDIA Y',
}


def is_noise(line: str) -> bool:
    if line in NOISE:
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
    return False


def is_question_start(line: str):
    return re.match(r'^(\d{1,3})\.[  \xa0]+(.+)', line)


def find_option_blocks(lines: list[str], start: int, end: int):
    """
    Scan lines[start:end] for option blocks.
    An option block is: {text}\n{LETTER}.\n{pct}% [Correct|Your]\n[Answer]
    Returns: (options_dict, correct_answer, respondent_stats, image_url, explanation_start_line)
    """
    options = {}
    correct_answer = None
    respondent_stats = {}
    image_url = None
    explanation_start = end

    i = start
    while i < end:
        line = lines[i].strip()

        # Skip empty/noise
        if not line or is_noise(line):
            i += 1
            continue

        # Skip image URLs but capture them
        if line.startswith('(https://'):
            if 'image' in line.lower() or 'axd' in line:
                image_url = line.strip('()')
            i += 1
            continue

        # Skip URL fragments (broken multi-line URLs)
        if re.match(r'^id=[a-f0-9]', line) or re.match(r'^[a-f0-9]{8}-', line):
            i += 1
            continue

        # Look for option text followed by LETTER.\npct%
        opt_text_parts = []
        j = i

        found_option = False
        while j < end:
            jline = lines[j].strip()

            # Check for letter marker "X." alone on a line
            letter_match = re.match(r'^([A-E])\.\s*$', jline)
            if letter_match:
                letter = letter_match.group(1)
                j += 1

                if j < end:
                    pct_line = lines[j].strip()
                    pct_match = re.match(r'^(\d+)%\s*(Correct|Your)?', pct_line)
                    if pct_match:
                        pct = int(pct_match.group(1))
                        respondent_stats[letter] = pct
                        is_correct_flag = pct_match.group(2) == 'Correct'
                        j += 1

                        # Check for "Answer" continuation
                        if j < end and lines[j].strip() == 'Answer':
                            if is_correct_flag:
                                correct_answer = letter
                            j += 1

                        opt_text = ' '.join(opt_text_parts).strip()
                        # Clean the option text
                        opt_text = re.sub(r'\s+', ' ', opt_text)
                        if opt_text and len(opt_text) > 0:
                            options[letter] = opt_text

                        found_option = True
                        i = j
                        break
                # If no valid pct line, skip
                i = j
                found_option = True
                break

            # Skip noise/empty within text collection
            if not jline or is_noise(jline):
                j += 1
                continue
            if jline.startswith('(https://'):
                j += 1
                continue
            if re.match(r'^id=[a-f0-9]', jline) or re.match(r'^[a-f0-9]{8}-', jline):
                j += 1
                continue

            opt_text_parts.append(jline)
            j += 1

        if not found_option:
            # No more options found; rest is explanation
            explanation_start = i
            break

        # Stop after collecting enough options (usually 4-5)
        if len(options) >= 5:
            explanation_start = i
            break

    if len(options) > 0 and explanation_start == end:
        explanation_start = i

    return options, correct_answer, respondent_stats, image_url, explanation_start


def collect_explanation(lines: list[str], start: int, end: int) -> str:
    """Collect explanation text from lines[start:end], skipping noise."""
    parts = []
    for k in range(start, end):
        line = lines[k].strip()
        if not line:
            continue
        if is_noise(line):
            continue
        if line.startswith('(https://'):
            continue
        if re.match(r'^id=[a-f0-9]', line) or re.match(r'^[a-f0-9]{8}-', line):
            continue
        if is_question_start(line):
            break
        parts.append(line)
    return ' '.join(parts)


def parse_all(lines: list[str], source_id: str) -> list[dict]:
    """
    Two-phase parser that handles the interleaved PDF layout.

    Phase 1: Find all question headers and collect question text.
    Phase 2: Find all option blocks and assign each to the correct question.
    """
    n = len(lines)

    # Phase 1: Find all question start positions and collect question text
    q_headers = []  # (line_idx, q_num, question_text)

    i = 0
    while i < n:
        line = lines[i].strip()
        m = is_question_start(line)
        if m:
            q_num = int(m.group(1))
            q_parts = [m.group(2).strip()]
            i += 1

            # Collect question text until noise/markers
            while i < n:
                line = lines[i].strip()
                if not line or is_noise(line):
                    break
                if line.startswith('(https://'):
                    break
                # Stop if next question starts
                if is_question_start(line):
                    break
                q_parts.append(line)
                i += 1

            question_text = ' '.join(q_parts)
            # Clean UI noise from question text
            question_text = re.sub(r'\s*[!\u201c\u201d"#$%]\s*', ' ', question_text)
            question_text = re.sub(r'\s+', ' ', question_text).strip()

            q_headers.append((i, q_num, question_text))
        else:
            i += 1

    # Phase 2: Find option blocks between consecutive question headers
    # The key insight: options for Q_N appear AFTER Q_N+1's header
    # So we scan between Q_N+1's header-end and Q_N+2's header-start
    # for Q_N's options.

    # But actually the pattern is more nuanced. Let me scan the ENTIRE
    # text for option blocks (sequences of text\nLETTER.\npct%) and
    # assign each block to the nearest preceding question that lacks options.

    # Simpler approach: for each pair of consecutive question headers,
    # the region BETWEEN them contains the options for the PREVIOUS question.

    # Build question objects
    questions = {}
    for idx, (line_idx, q_num, q_text) in enumerate(q_headers):
        questions[q_num] = {
            "id": q_num,
            "source": source_id,
            "question": q_text,
            "options": {},
            "correctAnswer": None,
            "explanation": "",
            "respondentStats": None,
            "imageUrl": None,
            "_header_end": line_idx,  # where question text collection ended
        }

    # For each question, find its options by scanning forward from its header
    # past the next question's header (where its options actually are)
    sorted_headers = sorted(q_headers, key=lambda x: x[0])  # sorted by line position

    for idx, (header_end, q_num, _) in enumerate(sorted_headers):
        # The search region for this question's options starts after the
        # question header noise, and extends until we find the options
        # (which may be after the NEXT question's header).

        # Determine search region:
        # Start: after our header
        # End: two questions ahead (to account for the interleaving)
        if idx + 2 < len(sorted_headers):
            search_end = sorted_headers[idx + 2][0]
        elif idx + 1 < len(sorted_headers):
            search_end = sorted_headers[idx + 1][0] + 100  # extend past next Q header
            search_end = min(search_end, n)
        else:
            search_end = n

        # Skip noise after our header to find where options region starts
        search_start = header_end
        while search_start < search_end:
            line = lines[search_start].strip()
            if not line or is_noise(line) or line.startswith('(https://'):
                search_start += 1
                continue
            if re.match(r'^id=[a-f0-9]', line) or re.match(r'^[a-f0-9]{8}-', line):
                search_start += 1
                continue
            # Check if this is a question header (skip it too)
            if is_question_start(line):
                search_start += 1
                # Skip that question's text too
                while search_start < search_end:
                    sl = lines[search_start].strip()
                    if not sl or is_noise(sl):
                        break
                    if is_question_start(sl):
                        break
                    search_start += 1
                continue
            break

        # Now scan for option blocks
        options, correct, stats, img_url, expl_start = find_option_blocks(
            lines, search_start, search_end
        )

        if options and len(options) >= 2:
            q = questions[q_num]
            q["options"] = dict(sorted(options.items()))
            q["correctAnswer"] = correct
            q["respondentStats"] = dict(sorted(stats.items())) if stats else None
            if img_url:
                q["imageUrl"] = img_url

            # Collect explanation
            # Explanation ends at the next question's options (two questions ahead)
            expl_end = search_end
            explanation = collect_explanation(lines, expl_start, expl_end)
            q["explanation"] = explanation

    # Clean up internal fields and filter
    result = []
    for q_num in sorted(questions.keys()):
        q = questions[q_num]
        del q["_header_end"]

        # Clean option texts
        for k in list(q["options"].keys()):
            text = q["options"][k]
            text = re.sub(r'[\ue000-\uf8ff]', '', text)  # private use chars
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                q["options"][k] = text
            else:
                del q["options"][k]

        # Clean explanation
        q["explanation"] = re.sub(r'\s+', ' ', q["explanation"]).strip()

        if len(q["options"]) >= 2 and len(q["question"]) > 10:
            result.append(q)

    return result


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

    print(f"Extracting text from: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    lines = text.split('\n')
    print(f"Extracted {len(text)} characters, {len(lines)} lines")

    source_id = "pediatric-bcsc"
    print("Parsing questions (V2 — interleave-aware)...")
    questions = parse_all(lines, source_id)

    # Deduplicate by ID
    seen = set()
    unique = []
    for q in questions:
        if q["id"] not in seen:
            seen.add(q["id"])
            unique.append(q)
    questions = sorted(unique, key=lambda q: q["id"])

    print(f"Parsed {len(questions)} unique questions")

    with_correct = sum(1 for q in questions if q["correctAnswer"])
    with_expl = sum(1 for q in questions if q["explanation"])
    with_stats = sum(1 for q in questions if q["respondentStats"])
    with_4opts = sum(1 for q in questions if len(q["options"]) >= 4)
    print(f"  With correct answer: {with_correct}")
    print(f"  With explanation: {with_expl}")
    print(f"  With respondent stats: {with_stats}")
    print(f"  With 4+ options: {with_4opts}")

    # Samples
    for q in questions[:5]:
        print(f"\n--- Q{q['id']} ---")
        print(f"  Q: {q['question'][:100]}")
        opts_preview = {k: v[:60] for k, v in q['options'].items()}
        print(f"  Opts: {opts_preview}")
        print(f"  Correct: {q['correctAnswer']}")

    # Missing IDs
    all_ids = set(range(1, 487))
    found_ids = {q["id"] for q in questions}
    missing = sorted(all_ids - found_ids)
    print(f"\nMissing IDs ({len(missing)}): {missing}")

    # Output
    output_dir = os.path.join(project_dir, "public", "data")
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, f"{source_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    print(f"\nJSON written to: {json_path}")

    manifest = {
        "questionSets": [{
            "id": source_id,
            "name": "Pediatric BCSC Self Assessment",
            "description": f"{len(questions)} questions on Pediatric Ophthalmology",
            "file": f"{source_id}.json",
            "questionCount": len(questions),
        }]
    }
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
