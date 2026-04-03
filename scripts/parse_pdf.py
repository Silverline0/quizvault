#!/usr/bin/env python3
"""
Parse the Pediatric BCSC Self Assessment PDF into structured JSON.

Uses PyMuPDF to extract text, then a state-machine parser.
Includes post-processing to clean up artifacts from overlapping PDF layouts.
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


# Noise lines to skip
NOISE = {
    '!', '"', '#', '$', '%', 'OFF', 'ON', 'Y',
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
    # Percentage bar lines (single or combined)
    if re.match(r'^(?:[A-E]\.\s*\d+%\s*)+$', line):
        return True
    return False


def is_question_start(line: str) -> re.Match | None:
    """Check if a line starts a new question."""
    return re.match(r'^(\d{1,3})\.[  \xa0]+(.+)', line)


def parse_questions(lines: list[str], source_id: str) -> list[dict]:
    """Parse all questions using a two-pass approach."""

    # Pass 1: Find all question start positions
    q_starts = []
    for i, line in enumerate(lines):
        m = is_question_start(line.strip())
        if m:
            q_starts.append((i, int(m.group(1)), m.group(2).strip()))

    questions = []

    for qi, (start_line, q_num, first_line_text) in enumerate(q_starts):
        # Determine the end of this question's block
        end_line = q_starts[qi + 1][0] if qi + 1 < len(q_starts) else len(lines)

        block_lines = [l.rstrip() for l in lines[start_line:end_line]]
        q = parse_single_question(block_lines, q_num, first_line_text, source_id)
        if q:
            questions.append(q)

    # Post-process: clean up all questions
    for q in questions:
        q["question"] = clean_text(q["question"])
        q["explanation"] = clean_text(q["explanation"])
        for k in list(q["options"].keys()):
            q["options"][k] = clean_option_text(q["options"][k])
            if not q["options"][k]:
                del q["options"][k]

    return questions


def parse_single_question(block_lines: list[str], q_num: int, first_text: str, source_id: str) -> dict | None:
    """Parse a single question from its block of lines."""

    # Collect question text
    q_parts = [first_text]
    i = 1  # skip first line (already extracted)

    while i < len(block_lines):
        line = block_lines[i].strip()
        if not line or is_noise(line):
            break
        # Stop at certain markers
        if line.startswith('(https://'):
            break
        q_parts.append(line)
        i += 1

    question_text = ' '.join(q_parts)

    # Skip noise section until options
    while i < len(block_lines):
        line = block_lines[i].strip()
        if not line or is_noise(line) or line.startswith('(https://'):
            i += 1
            continue
        break

    # Parse options
    options = {}
    correct_answer = None
    respondent_stats = {}
    image_url = None

    # Collect all remaining lines into a single string for option parsing
    remaining = '\n'.join(block_lines[i:])

    # Extract image URL
    img_match = re.search(r'\(https?://[^\)]+\)', remaining)
    if img_match:
        image_url = img_match.group(0).strip('()')

    # Find option patterns: text followed by "LETTER.\npct%"
    # or "LETTER.\npct% Correct\nAnswer"
    # Pattern: capture everything before a "X.\n" line as option text
    option_pattern = re.compile(
        r'(.+?)\n([A-E])\.\n(\d+)%(?: (Correct|Your))?\n?(Answer)?',
        re.DOTALL
    )

    # First, collect percentage stats from the remaining text
    for m in re.finditer(r'([A-E])\.\s*(\d+)%', remaining):
        letter = m.group(1)
        pct = int(m.group(2))
        if letter not in respondent_stats:
            respondent_stats[letter] = pct

    # Find option text blocks
    # Strategy: scan line by line for the pattern:
    #   some text lines
    #   LETTER.
    #   pct% [Correct|Your]
    #   [Answer]
    block_i = i
    while block_i < len(block_lines):
        line = block_lines[block_i].strip()

        # Skip noise and empty
        if not line or is_noise(line):
            block_i += 1
            continue

        # Skip image URLs
        if line.startswith('(https://'):
            if 'image' in line.lower() or 'axd' in line:
                image_url = line.strip('()')
            block_i += 1
            continue

        # Check if this could be option text
        # Look ahead for "LETTER." pattern
        opt_text_parts = []
        j = block_i

        while j < len(block_lines):
            jline = block_lines[j].strip()

            # Found a letter marker
            letter_match = re.match(r'^([A-E])\.\s*$', jline)
            if letter_match:
                letter = letter_match.group(1)
                j += 1

                # Next should be pct% line
                if j < len(block_lines):
                    pct_line = block_lines[j].strip()
                    pct_match = re.match(r'^(\d+)%\s*(Correct|Your)?', pct_line)
                    if pct_match:
                        pct = int(pct_match.group(1))
                        respondent_stats[letter] = pct
                        is_correct = pct_match.group(2) == 'Correct'
                        is_your = pct_match.group(2) == 'Your'
                        j += 1

                        # Check for "Answer" continuation
                        if j < len(block_lines) and block_lines[j].strip() == 'Answer':
                            if is_correct:
                                correct_answer = letter
                            j += 1

                        opt_text = ' '.join(opt_text_parts).strip()
                        if opt_text:
                            options[letter] = opt_text

                block_i = j
                break

            # Skip noise within option text collection
            if not jline or is_noise(jline):
                j += 1
                continue
            if jline.startswith('(https://'):
                j += 1
                continue

            opt_text_parts.append(jline)
            j += 1
        else:
            # No letter marker found - rest is explanation
            break

        # If we have 4+ options, the rest is likely explanation
        if len(options) >= 5:
            break

    # Collect explanation: everything after options until end of block
    explanation_parts = []
    for k in range(block_i, len(block_lines)):
        line = block_lines[k].strip()
        if not line:
            continue
        if is_noise(line):
            continue
        if line.startswith('(https://'):
            continue
        # Stop if we see another question start embedded
        if is_question_start(line):
            break
        explanation_parts.append(line)

    explanation = ' '.join(explanation_parts)

    if len(options) < 2 or len(question_text) < 10:
        return None

    return {
        "id": q_num,
        "source": source_id,
        "question": question_text,
        "options": dict(sorted(options.items())),
        "correctAnswer": correct_answer,
        "explanation": explanation,
        "respondentStats": dict(sorted(respondent_stats.items())) if respondent_stats else None,
        "imageUrl": image_url,
    }


def clean_text(text: str) -> str:
    """Clean question/explanation text."""
    # Remove UI noise characters
    text = re.sub(r'\s*[!""#$%]\s*', ' ', text)
    # Remove embedded question patterns (from overlapping layout)
    text = re.sub(r'\d{1,3}\.[  \xa0]+[A-Z].*?\?\s*', '', text)
    # Remove percentage patterns
    text = re.sub(r'[A-E]\.\s*\d+%\s*', '', text)
    # Remove image URLs
    text = re.sub(r'\(https?://[^\)]+\)', '', text)
    # Clean up
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_option_text(text: str) -> str:
    """Clean individual option text."""
    # Remove embedded question text (number. text?)
    text = re.sub(r'\d{1,3}\.[  \xa0]+[A-Z].*?\?.*?(?=[a-z])', '', text, flags=re.DOTALL)
    # Remove percentage patterns
    text = re.sub(r'[A-E]\.\s*\d+%\s*', '', text)
    # Remove image URLs and fragments
    text = re.sub(r'\(https?://[^\)]+\)', '', text)
    text = re.sub(r'id=[a-f0-9\-]+&?[^\s]*', '', text)
    # Remove UI noise
    text = re.sub(r'\s*[!""#$%]\s*', ' ', text)
    text = re.sub(r'\b(Explanation\s*&?\s*Notes|Discussion|BCSC\s*Excerpt|References|Notes|ON|OFF)\b', '', text)
    # Remove special characters
    text = re.sub(r'[\ue000-\uf8ff]', '', text)  # Private use area chars
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    # Find the PDF
    pdf_path = None
    for pattern in ["Pediatric*BCSC*.pdf", "Pediatric*.pdf"]:
        matches = glob.glob(os.path.join(project_dir, pattern))
        if matches:
            pdf_path = matches[0]
            break

    if not pdf_path or not os.path.exists(pdf_path):
        print("PDF not found!")
        sys.exit(1)

    print(f"Extracting text from: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    lines = text.split('\n')
    print(f"Extracted {len(text)} characters, {len(lines)} lines")

    source_id = "pediatric-bcsc"
    print("Parsing questions...")
    questions = parse_questions(lines, source_id)

    # Deduplicate by ID (keep first occurrence)
    seen_ids = set()
    unique_questions = []
    for q in questions:
        if q["id"] not in seen_ids:
            seen_ids.add(q["id"])
            unique_questions.append(q)
    questions = sorted(unique_questions, key=lambda q: q["id"])

    print(f"Parsed {len(questions)} unique questions")

    # Quality stats
    with_correct = sum(1 for q in questions if q["correctAnswer"])
    with_explanation = sum(1 for q in questions if q["explanation"])
    with_stats = sum(1 for q in questions if q["respondentStats"])
    with_4_opts = sum(1 for q in questions if len(q["options"]) >= 4)
    print(f"  With correct answer: {with_correct}")
    print(f"  With explanations: {with_explanation}")
    print(f"  With respondent stats: {with_stats}")
    print(f"  With 4+ options: {with_4_opts}")

    # Print samples
    for q in questions[:3]:
        print(f"\n--- Q{q['id']} ---")
        print(f"  Q: {q['question'][:100]}")
        print(f"  Options: { {k: v[:50] for k, v in q['options'].items()} }")
        print(f"  Correct: {q['correctAnswer']}")

    if len(questions) > 50:
        q = questions[49]
        print(f"\n--- Q{q['id']} (sample #50) ---")
        print(f"  Q: {q['question'][:100]}")
        print(f"  Options: { {k: v[:50] for k, v in q['options'].items()} }")
        print(f"  Correct: {q['correctAnswer']}")

    # Missing IDs
    all_ids = set(range(1, 487))
    found_ids = {q["id"] for q in questions}
    missing = sorted(all_ids - found_ids)
    if missing:
        print(f"\nMissing IDs ({len(missing)}): {missing}")

    # Output
    output_dir = os.path.join(project_dir, "public", "data")
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, f"{source_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    print(f"\nJSON written to: {json_path}")

    manifest = {
        "questionSets": [
            {
                "id": source_id,
                "name": "Pediatric BCSC Self Assessment",
                "description": f"{len(questions)} questions on Pediatric Ophthalmology",
                "file": f"{source_id}.json",
                "questionCount": len(questions),
            }
        ]
    }
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
