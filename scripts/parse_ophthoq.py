#!/usr/bin/env python3
"""
Parser for OphthoQ PDF files — handles multiple format variants:

Format A (Fundamentals): "1. Q text\nA. opt\nB. opt\nC. Summary...(correct)"
Format B (Cornea): "Q- Q text\nA.opt\nB.opt\nA:B"
Format C (Pedia HY/Lens): "1- Q text\nA.opt\nB.opt\n\nB. explanation"
Format D (Neuro/Retina): "Q text?\nA.opt\nB.opt\nCorrect Answer:\nD\nExplanation:"
Format E (Uveitis): "Q text?\nA. opt\nAnswer : D"

Strategy: detect answer-marker style first, then parse accordingly.
"""

import json
import re
import sys
import os
import glob


def extract_text_from_pdf(pdf_path: str) -> list[str]:
    import fitz
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.split('\n')


def extract_images_from_pdf(pdf_path: str, source_id: str):
    import fitz
    images_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "public", "images", source_id
    )
    os.makedirs(images_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    page_images = {}
    img_count = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        for img_idx, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                if pix.width < 50 or pix.height < 50:
                    continue
                img_filename = f"p{page_num+1}_img{img_idx+1}.png"
                img_path = os.path.join(images_dir, img_filename)
                pix.save(img_path)
                if page_num not in page_images:
                    page_images[page_num] = []
                page_images[page_num].append(f"/images/{source_id}/{img_filename}")
                img_count += 1
            except Exception:
                continue
    doc.close()
    return page_images, img_count


def detect_format(lines: list[str]) -> str:
    """Detect which OphthoQ format variant this file uses."""
    answer_colon = 0      # "Answer : D" or "Answer :D"
    correct_answer = 0    # "Correct Answer:\nD"
    a_colon_letter = 0    # "A:B" or "A: C"
    letter_dot_expl = 0   # "B. explanation text" (answer is first letter of explanation)

    for i, l in enumerate(lines):
        s = l.strip()
        if re.match(r'^Answer\s*:\s*[A-E]', s, re.I):
            answer_colon += 1
        if re.match(r'^Correct\s*Answer\s*:', s, re.I):
            correct_answer += 1
        if re.match(r'^A\s*:\s*[A-E]\b', s):
            a_colon_letter += 1

    if correct_answer > 10:
        return "correct_answer_multiline"  # Neuro, Retina style
    elif answer_colon > 10:
        return "answer_colon"  # Uveitis style
    elif a_colon_letter > 10:
        return "a_colon"  # Cornea style
    else:
        return "letter_explanation"  # Pedia, Lens, Fundamentals style


def is_option_line(line: str) -> tuple:
    """Check if line starts an option. Returns (letter, text) or None."""
    # Match "A. text" or "A.text" — but NOT "A. " alone and NOT "A:" patterns
    m = re.match(r'^([A-E])[\.\)]\s*(.*)', line)
    if m and m.group(2).strip():
        return m.group(1), m.group(2).strip()
    # Also match "• A. text" (bullet prefix)
    m2 = re.match(r'^[•\-]\s*([A-E])[\.\)]\s*(.*)', line)
    if m2 and m2.group(2).strip():
        return m2.group(1), m2.group(2).strip()
    return None


def is_question_start(line: str):
    """Check for numbered question: 1. or Q1. or 1- or Q- etc."""
    # "1. text" or "Q1. text"
    m = re.match(r'^Q?(\d{1,3})[.\-–]\s*(.+)', line)
    if m:
        return int(m.group(1)), m.group(2).strip()
    # "Q- text" or "Q – text"
    m2 = re.match(r'^Q\s*[-–]\s*(.+)', line)
    if m2:
        return -1, m2.group(1).strip()  # -1 = no number, needs auto-assign
    return None


def parse_universal(lines: list[str], source_id: str, fmt: str, page_images=None) -> list[dict]:
    """Universal parser that handles all OphthoQ format variants."""
    questions = []
    n = len(lines)
    q_counter = 0

    # For unnumbered formats, we find questions by looking for option blocks
    # (A. B. C. D. in sequence) preceded by question text

    i = 0
    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Skip page numbers, section headers
        if re.match(r'^pg\.\s*\d+', line, re.I) or re.match(r'^\d+$', line):
            i += 1
            continue

        # Try to find a question start
        q_start = is_question_start(line)

        # For formats with no numbered questions (Uveitis, some Neuro),
        # detect question by finding text followed by A./B./C./D. options
        if not q_start:
            # Look ahead: if next non-empty lines have A. B. C. D. pattern, this is a question
            has_options = False
            for j in range(i + 1, min(i + 8, n)):
                sl = lines[j].strip()
                if is_option_line(sl):
                    has_options = True
                    break

            if has_options and len(line) > 15 and line[0].isupper() and '?' in line or (
                has_options and len(line) > 15 and i + 1 < n and '?' in ' '.join(lines[i:i+3])
            ):
                q_start = (-1, line)
                i += 1
            else:
                i += 1
                continue
        else:
            i += 1

        q_num, first_text = q_start
        if q_num == -1:
            q_counter += 1
            q_num = q_counter
        else:
            q_counter = q_num

        # Collect question text until options start
        q_parts = [first_text]
        while i < n:
            sl = lines[i].strip()
            if not sl:
                i += 1
                continue
            if is_option_line(sl):
                break
            if is_question_start(sl):
                break
            if re.match(r'^pg\.\s*\d+', sl, re.I):
                i += 1
                continue
            q_parts.append(sl)
            i += 1

        question_text = ' '.join(q_parts)
        question_text = re.sub(r'\s+', ' ', question_text).strip()

        if len(question_text) < 10:
            continue

        # Parse options
        options = {}
        while i < n:
            sl = lines[i].strip()
            if not sl:
                i += 1
                continue

            opt = is_option_line(sl)
            if opt:
                letter, opt_text = opt
                i += 1
                # Continue option text on next lines
                while i < n:
                    nl = lines[i].strip()
                    if not nl:
                        break
                    if is_option_line(nl):
                        break
                    if is_question_start(nl):
                        break
                    if re.match(r'^(Correct\s*Answer|High\s*Yield|Explanation|Answer\s*:)', nl, re.I):
                        break
                    if re.match(r'^A\s*:\s*[A-E]', nl):
                        break
                    opt_text += ' ' + nl
                    i += 1
                opt_text = re.sub(r'\s+', ' ', opt_text).strip()
                options[letter] = opt_text
            else:
                break

        if len(options) < 2:
            continue

        # Find correct answer based on format
        correct_answer = None
        high_yield = None
        explanation_parts = []

        # Scan for answer marker
        scan_end = min(i + 20, n)
        while i < scan_end:
            sl = lines[i].strip()

            if not sl:
                i += 1
                continue

            # "Answer : D" or "Answer :D" or "Answer: D"
            am = re.match(r'^Answer\s*:\s*([A-E])', sl, re.I)
            if am:
                correct_answer = am.group(1).upper()
                i += 1
                continue

            # "A:B" or "A: C"
            am2 = re.match(r'^A\s*:\s*([A-E])\b', sl)
            if am2:
                correct_answer = am2.group(1).upper()
                i += 1
                continue

            # "Correct Answer:\n D" (multiline)
            if re.match(r'^Correct\s*Answer\s*:', sl, re.I):
                i += 1
                while i < n:
                    nl = lines[i].strip()
                    if nl and re.match(r'^([A-E])\s*$', nl):
                        correct_answer = nl[0].upper()
                        i += 1
                        break
                    elif nl:
                        break
                    i += 1
                continue

            # "High Yield: Yes/No" or multiline "High Yield:\nYes"
            hm = re.match(r'^High\s*Yield\s*:\s*(Yes|No)?', sl, re.I)
            if hm:
                if hm.group(1):
                    high_yield = hm.group(1).lower() == 'yes'
                else:
                    i += 1
                    if i < n:
                        val = lines[i].strip()
                        if val.lower() in ('yes', 'no'):
                            high_yield = val.lower() == 'yes'
                            i += 1
                continue

            # "Explanation:" marker
            if re.match(r'^Explanation\s*:', sl, re.I):
                i += 1
                continue

            # If no markers found yet and this looks like "B. explanation text..."
            # (letter-dot-space starting the explanation = the answer)
            if not correct_answer:
                lm = re.match(r'^([A-E])\.\s+[A-Z]', sl)
                if lm and lm.group(1) in options:
                    correct_answer = lm.group(1)
                    # Rest of line is explanation
                    explanation_parts.append(re.sub(r'^[A-E]\.\s*', '', sl))
                    i += 1
                    break

            # If none of the markers matched, this might be explanation already
            break

        # Collect explanation
        while i < n:
            sl = lines[i].strip()
            if is_question_start(sl):
                break
            # Check for unnumbered question start (text + options ahead)
            if sl and len(sl) > 15 and sl[0].isupper():
                has_opts = False
                for j in range(i + 1, min(i + 6, n)):
                    if lines[j].strip() and is_option_line(lines[j].strip()):
                        has_opts = True
                        break
                if has_opts and '?' in sl:
                    break

            if re.match(r'^pg\.\s*\d+', sl, re.I):
                i += 1
                continue
            if sl:
                explanation_parts.append(sl)
            i += 1

        explanation = ' '.join(explanation_parts)
        explanation = re.sub(r'^[A-E]\.\s*', '', explanation)
        explanation = re.sub(r'High\s*Yield\s*:\s*(Yes|No)\s*', '', explanation, flags=re.I)
        explanation = re.sub(r'Correct\s*Answer\s*:\s*[A-E]\s*', '', explanation, flags=re.I)
        explanation = re.sub(r'Explanation\s*:\s*', '', explanation, flags=re.I)
        explanation = re.sub(r'\s+', ' ', explanation).strip()

        questions.append({
            "id": q_num,
            "source": source_id,
            "question": question_text,
            "options": dict(sorted(options.items())),
            "correctAnswer": correct_answer,
            "explanation": explanation,
            "respondentStats": None,
            "imageUrl": None,
            "highYield": high_yield,
        })

    return questions


# ── Batch configuration ────────────────────────────────────────────

OPHTHOQ_FILES = [
    {"pattern": "1 - Fundamentals*OphthoQ*", "source_id": "fundamentals-oq",
     "name": "Fundamentals (OphthoQ)", "category": "fundamentals"},
    {"pattern": "2 - Cornea*Ophtha*", "source_id": "cornea-oq",
     "name": "Cornea (OphthoQ)", "category": "cornea"},
    {"pattern": "3*Lens*Cataract*OphthoQ*", "source_id": "lens-cataract-oq",
     "name": "Lens & Cataract (OphthoQ)", "category": "lens-cataract"},
    {"pattern": "5 - Pedia*High*Yield*", "source_id": "pedia-hy-oq",
     "name": "Pediatrics High Yield (OphthoQ)", "category": "pediatrics"},
    {"pattern": "5 - Uveitis*OQ*", "source_id": "uveitis-oq",
     "name": "Uveitis (OphthoQ)", "category": "uveitis"},
    {"pattern": "6 - Pedia*Non*High*Yield*", "source_id": "pedia-nhy-oq",
     "name": "Pediatrics Non-HY (OphthoQ)", "category": "pediatrics"},
    {"pattern": "7 - Retina*OQ*", "source_id": "retina-oq",
     "name": "Retina (OphthoQ)", "category": "retina"},
    {"pattern": "8*neuro*OQ*", "source_id": "neuro-oq",
     "name": "Neuro-Ophthalmology (OphthoQ)", "category": "neuro"},
]


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    output_dir = os.path.join(project_dir, "public", "data")
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for cfg in OPHTHOQ_FILES:
        matches = glob.glob(os.path.join(project_dir, cfg["pattern"] + ".pdf"))
        if not matches:
            print(f"  SKIP: No file matching '{cfg['pattern']}'")
            continue

        pdf_path = matches[0]
        print(f"\n{'='*60}")
        print(f"Parsing: {cfg['name']} ({cfg['source_id']})")

        lines = extract_text_from_pdf(pdf_path)
        print(f"  {len(lines)} lines")

        fmt = detect_format(lines)
        print(f"  Detected format: {fmt}")

        print("  Extracting images...")
        page_images, img_count = extract_images_from_pdf(pdf_path, cfg["source_id"])
        print(f"  {img_count} images extracted")

        questions = parse_universal(lines, cfg["source_id"], fmt, page_images)

        # Deduplicate
        seen = set()
        unique = []
        for q in questions:
            if q["id"] not in seen:
                seen.add(q["id"])
                unique.append(q)
        questions = sorted(unique, key=lambda q: q["id"])

        with_correct = sum(1 for q in questions if q["correctAnswer"])
        with_4opts = sum(1 for q in questions if len(q["options"]) >= 4)

        print(f"  Result: {len(questions)} questions, {with_correct} with correct answer, {with_4opts} with 4+ options")

        # Show first 2
        for q in questions[:2]:
            print(f"    Q{q['id']}: {q['question'][:60]}...")
            for k, v in sorted(q['options'].items()):
                marker = ' <<<' if k == q['correctAnswer'] else ''
                print(f"      {k}: {v[:50]}{marker}")

        json_path = os.path.join(output_dir, f"{cfg['source_id']}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        results.append({
            "id": cfg["source_id"],
            "name": cfg["name"],
            "category": cfg["category"],
            "file": f"{cfg['source_id']}.json",
            "questionCount": len(questions),
            "source": "OphthoQ",
        })

    print(f"\n{'='*60}")
    print("OPHTHOQ BATCH SUMMARY")
    total = sum(r["questionCount"] for r in results)
    for r in results:
        print(f"  {r['name']}: {r['questionCount']} questions")
    print(f"  TOTAL: {total} questions across {len(results)} sets")

    meta_path = os.path.join(output_dir, "_ophthoq_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
