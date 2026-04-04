#!/usr/bin/env python3
"""
Fix truncated explanations in OphthoQ JSON files by finding
continuation text in the corresponding PDF files.

Two fix types:
1. APPEND: Find continuation text in PDF and append it.
2. PERIOD: Add missing terminal punctuation when explanation is already complete.
"""
import json
import re
import sys
import os

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install PyMuPDF")
    sys.exit(1)

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "public", "data")

FILE_MAP = [
    ("cornea-oq.json",        "2 - Cornea Ophtha.pdf"),
    ("pedia-hy-oq.json",      "5 - Pedia High Yield Questions .pdf"),
    ("neuro-oq.json",         "8 - neuro OQ.pdf"),
    ("retina-oq.json",        "7 - Retina - OQ.pdf"),
    ("fundamentals-oq.json",  "1 - Fundamentals - OphthoQ.pdf"),
    ("pedia-nhy-oq.json",     "6 - Pedia Non-High Yield Questions .pdf"),
    ("uveitis-oq.json",       "5 - Uveitis OQ.pdf"),
    ("lens-cataract-oq.json", "3- Lens and Cataract OphthoQ.pdf"),
]

# Characters that mark a properly-ended explanation (colon included intentionally)
GOOD_ENDINGS = set('.?!"\u2019):')

SECTION_HEADERS = [
    'Structure and Function', 'Examination Techniques',
    'Corneal Dystrophies and Ectasias', 'Corneal Dystrophies',
    'Depositions and Degenerations', 'Depositions and Degeneration',
    'Ocular Immunology Diseases', 'Ocular Immunology',
    'Immune-related Disorders of the External Eye', 'Immune-related Disorders',
    'Ocular Surface Diseases', 'Congenital Orbital Anomalies',
    'Metabolic Disorders with Corneal Manifestations', 'Metabolic Disorders',
    'Microbial and parasitic infection', 'Viral Infections',
    'Neoplastic Disorder', 'Toxic and Traumatic Corneal Changes',
    'Toxic and Traumatic', 'Corneal Transplant', 'Ocular Surgery',
    'Cataract Surgery', 'ANATOMY', 'Physiology', 'Growth/Development',
    'Growth', 'Strabismus/Amblyopia', 'Strabismus', 'Nystagmus/Diplopia',
    'Nystagmus', 'Corneal Abnormalities', 'Glaucoma', 'Iris Abnormalities',
    'Cataract/Lens Disorders', 'Cataract', 'Uveitis', 'Retina',
    'Optic Disc Abnormalities', 'Optic Disc', 'Oculoplasty',
    'Phakomatoses', 'Infectious/Allergies', 'Infectious',
    'Other Questions', 'Embryology', 'Pathology', 'Surgery',
    'Neuroanatomy', 'Afferent Visual Pathways', 'Efferent Visual Pathways',
    'The Pupil', 'Eyelid or Facial Abnormalities', 'Eyelid', 'Diplopia',
    'Nonorganic Ophthalmic Disorders', 'Nonorganic',
    'Rheumatic disorder', 'Selected Systemic Conditions',
    'Selected Systemic Conditions with Neuro-ophthalmic Signs',
    'The Patient with Eyelid Or Facial Abnormalities',
    'The Patient with Decreased Vision', 'Amblyopia',
    'Illusions, Hallucinations, and Disorders of Higher Cortical Function',
    'Disorders of Higher Cortical Function',
    'Development', 'Anatomy', 'Physiology of Vision',
    'Retinal Diagnostics', 'Retinal Vascular Disease',
    'Acquired Macular Disorders', 'Hereditary Retinal and Choroidal Dystrophies',
    'Retinal Detachment', 'Tumors', 'Peripheral Retinal Abnormalities',
    'Surgical Retina', 'Pathologic Myopia',
    'Orbit', 'Blood Vessels', 'Muscles', 'Nerves', 'Eyelids',
    'Lacrimal System', 'Conjunctiva', 'Cornea and Sclera',
    'Uveal Tract', 'Lens', 'Vitreous', 'Retina and RPE',
    'Visual Pathways', 'Cranial nerves', 'Biochemistry',
    'Genetics', 'Pharmacology', 'Glaucoma Drugs',
    'Cholinergic & Adrenergic Drugs', 'Anesthesia', 'Others',
    'Anomalies of Lens Shape', 'Ectopia Lentis',
    'Age-Related (Senile) Cataract', 'Other Forms of Cataract',
    'Intraocular Lenses', 'Preoperative Evaluation',
    'Cataract Surgery Techniques', 'Complications',
    'Anterior Uveitis', 'Intermediate Uveitis', 'Posterior Uveitis',
    'Panuveitis', 'Endophthalmitis',
    'Amblyopia and Strabismus', 'Pediatric Cataracts',
    'Pediatric Glaucoma', 'ROP', 'Genetic Diseases',
    'The Choroid', 'Diagnostic Approach to Retinal Disease',
]

BOUNDARY_PATTERNS = [
    r'Q-\s*[A-Z]',
    r'Q\d+-',
    r'Correct Answer:\s*',
    r'High Yield:\s*',
    r'Answer\s*:\s*[A-D]\b',   # Uveitis-style "Answer : C"
]

OPTION_BLOCK_RE = re.compile(
    r'(?<!\w)A\.'
    r'[^Q]{3,150}?'
    r'B\.'
    r'[^Q]{3,150}?'
    r'C\.'
    r'[^Q]{3,150}?'
    r'D\.'
)

Q_STARTERS = re.compile(
    r'(?:Which|What|How|Where|When|Why|Who|In which|All of the following|'
    r'A patient|An? \d|The (?:most|least|following|patient|primary|main|best)|'
    r'Regarding|Concerning|True or|Select|Choose|Identify|Name|Describe|'
    r'If (?:a|the)|During|After|Before|According|Compared|With respect|'
    r'Each of|None of|One of|Most of|Approximately|You are|'
    r'Below|Above|An? (?:increase|decrease)|The (?:risk|most common|classic))'
)


def extract_pdf_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def normalize(text):
    return re.sub(r'\s+', ' ', text).strip()


def strip_trailing_headers(text):
    """Remove trailing section headers and page numbers."""
    changed = True
    while changed:
        changed = False
        t = text.rstrip()
        for header in sorted(SECTION_HEADERS, key=len, reverse=True):
            if t.endswith(header):
                t = t[:-len(header)].rstrip()
                changed = True
                break
        m = re.search(r'\s+\d{1,3}\s*$', t)
        if m:
            t = t[:m.start()].rstrip()
            changed = True
        text = t
    return text


def clean_text(text):
    """Clean extracted text from PDF artifacts."""
    text = re.sub(r'^\s*Extra:\s*', '', text)
    text = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\bpg\.\s*\d+\b', '', text, flags=re.IGNORECASE)
    text = normalize(text)
    text = strip_trailing_headers(text)
    text = re.sub(r'\s+\d{1,3}\s*$', '', text).strip()
    return text


def find_next_boundary(remaining):
    """
    Find where the next question starts in remaining text.
    Returns an index into `remaining`.
    """
    best = len(remaining)

    # Try all boundary patterns
    for pat in BOUNDARY_PATTERNS:
        m = re.search(pat, remaining)
        if m and m.start() < best:
            best = m.start()

    # Try the answer option block
    m = OPTION_BLOCK_RE.search(remaining)
    if m:
        before_options = remaining[:m.start()].strip()
        last_q_mark = before_options.rfind('?')

        if last_q_mark >= 0:
            # Find where the question sentence starts in `remaining`
            before_q = remaining[:last_q_mark + 1]
            q_matches = list(Q_STARTERS.finditer(before_q))
            if q_matches:
                q_start = q_matches[-1].start()
                # q_start is the index in `remaining` where question text starts
                # But there may be section headers between explanation and question
                pre_text = remaining[:q_start].rstrip()
                stripped = strip_trailing_headers(pre_text)
                # The boundary is where the stripped text ends
                # But we need the index in `remaining`, not the length of stripped text
                # Find the start of the section header in remaining
                candidate = len(stripped) if stripped else 0
                # candidate=0 means header consumed all text before the question
                # In that case, there's no continuation -- set boundary to 0
                if candidate < best:
                    best = candidate
            else:
                last_period = max(before_options.rfind('.'), before_options.rfind(':'))
                if last_period >= 0 and last_period + 1 < best:
                    best = last_period + 1
        else:
            if m.start() < best:
                best = m.start()

    # Try numbered question patterns
    m = re.search(r'\d{1,3}[-\.]\s+[A-Z]', remaining)
    if m and m.start() < best:
        best = m.start()

    return best


def find_continuation(explanation, pdf_norm):
    """
    Find continuation text for a truncated explanation.
    Returns (continuation_text, found_in_pdf).
    """
    exp = explanation.strip()
    search_exp = exp
    has_extra = False
    if search_exp.endswith('Extra:'):
        has_extra = True
        search_exp = search_exp[:-len('Extra:')].strip()

    for nlen in [80, 60, 40, 30, 25, 20, 15, 12, 10]:
        if len(search_exp) < nlen:
            continue

        needle = normalize(search_exp[-nlen:])

        # Find ALL occurrences of the needle in the PDF
        occurrences = []
        start = 0
        while True:
            idx = pdf_norm.find(needle, start)
            if idx < 0:
                break
            occurrences.append(idx)
            start = idx + 1

        if not occurrences:
            continue

        # Try each occurrence, preferring the one that gives the shortest
        # valid continuation (the LAST match is usually the truncation point)
        best_cont = None
        found_any = False
        for idx in reversed(occurrences):
            end_pos = idx + len(needle)
            remaining = pdf_norm[end_pos:]

            # Skip Extra: marker in PDF
            if has_extra:
                m = re.match(r'\s*Extra:\s*', remaining)
                if m:
                    remaining = remaining[m.end():]

            # Find next question boundary
            boundary = find_next_boundary(remaining)
            cont_raw = remaining[:boundary].strip()

            # Clean
            cont = clean_text(cont_raw)
            found_any = True

            if len(cont) > 3:
                if best_cont is None or len(cont) < len(best_cont):
                    best_cont = cont
                # The last (reversed = first tried) match usually gives best result
                break

        if best_cont:
            return best_cont, True
        elif found_any:
            return None, True

    return None, False


def get_questions(data):
    if isinstance(data, list):
        return [q for q in data if isinstance(q, dict)]
    elif isinstance(data, dict) and 'questions' in data:
        return data['questions']
    return []


def process_file(json_filename, pdf_filename):
    json_path = os.path.join(DATA_DIR, json_filename)
    pdf_path = os.path.join(BASE, pdf_filename)

    if not os.path.exists(json_path):
        print(f"  SKIP: {json_path} not found")
        return 0, 0, 0, 0
    if not os.path.exists(pdf_path):
        print(f"  SKIP: {pdf_path} not found")
        return 0, 0, 0, 0

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    questions = get_questions(data)
    if not questions:
        print(f"  SKIP: no questions")
        return 0, 0, 0, 0

    pdf_text = extract_pdf_text(pdf_path)
    pdf_norm = normalize(pdf_text)

    appended = 0
    period_added = 0
    not_found = 0

    for q in questions:
        exp = (q.get('explanation', '') or '').strip()
        if not exp:
            continue

        # Pre-clean: strip trailing bullet chars, Extra:, section headers, page numbers
        cleaned_exp = exp.rstrip()
        cleaned_exp = cleaned_exp.rstrip('\u2022\u25cf\u2023\u25aa\u25cb\u00b7\u2013\u2014\u2018')
        cleaned_exp = cleaned_exp.rstrip()
        if cleaned_exp.endswith('Extra:'):
            cleaned_exp = cleaned_exp[:-len('Extra:')].rstrip()
        cleaned_exp = strip_trailing_headers(cleaned_exp)
        cleaned_exp = re.sub(r'\s+\d{1,3}\s*$', '', cleaned_exp).strip()

        # If after cleanup the explanation ends properly, just save cleaned version
        if cleaned_exp and cleaned_exp[-1] in GOOD_ENDINGS:
            if cleaned_exp != exp:
                q['explanation'] = cleaned_exp
                period_added += 1
            continue

        # Still truncated -- try to find continuation in PDF
        continuation, found_in_pdf = find_continuation(exp, pdf_norm)

        if continuation:
            new_exp = cleaned_exp + ' ' + continuation
            new_exp = strip_trailing_headers(new_exp).strip()
            if new_exp and new_exp[-1] not in GOOD_ENDINGS:
                new_exp += '.'
            q['explanation'] = new_exp
            appended += 1
        else:
            if cleaned_exp and cleaned_exp[-1] not in GOOD_ENDINGS:
                cleaned_exp += '.'
            q['explanation'] = cleaned_exp
            if found_in_pdf:
                period_added += 1
            else:
                not_found += 1

    # Save
    if appended > 0 or period_added > 0 or not_found > 0:
        if isinstance(data, list):
            idx = 0
            for i, item in enumerate(data):
                if isinstance(item, dict) and idx < len(questions):
                    data[i] = questions[idx]
                    idx += 1
        elif isinstance(data, dict) and 'questions' in data:
            data['questions'] = questions

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return appended, period_added, not_found, len(questions)


def main():
    print("=" * 60)
    print("Fix Truncated Explanations in OphthoQ JSON Files")
    print("=" * 60)

    total_app = 0
    total_per = 0
    total_nf = 0

    for json_file, pdf_file in FILE_MAP:
        print(f"\nProcessing: {json_file}")
        print(f"  PDF: {pdf_file}")
        app, per, nf, total = process_file(json_file, pdf_file)
        total_app += app
        total_per += per
        total_nf += nf
        print(f"  Questions: {total}")
        print(f"  Appended from PDF: {app}")
        print(f"  Period added: {per}")
        print(f"  Not found (period added): {nf}")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY:")
    print(f"  Continuations appended from PDF: {total_app}")
    print(f"  Periods added (missing punctuation): {total_per}")
    print(f"  Not found in PDF (period added): {total_nf}")
    print(f"  TOTAL FIXES: {total_app + total_per + total_nf}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
