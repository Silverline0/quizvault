#!/usr/bin/env python3
"""
Link unlinked PDF images to questions as secondary images (imageUrls).

For each OphthoQ JSON + PDF pair:
1. Extract per-page text from the PDF
2. For each page that has images NOT already linked as a question's imageUrl:
   - Normalize the page text and each question's text (lowercase, no punct, first 8 words)
   - If a question matches the page, add the unlinked images to imageUrls
   - If no match on the current page, try matching the PREVIOUS page's question
     (explanation images often appear on the page after the question)
3. Save the updated JSON
"""

import json
import os
import re
import sys
import glob
import unicodedata


def normalize(text: str, word_count: int = 8) -> str:
    """Lowercase, strip punctuation, take first N words."""
    text = text.lower()
    # Remove accents
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()[:word_count]
    return ' '.join(words)


def extract_page_texts(pdf_path: str) -> dict:
    """Extract text per page from PDF. Returns {page_num_1based: text}."""
    import fitz
    doc = fitz.open(pdf_path)
    page_texts = {}
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        page_texts[page_num + 1] = text  # 1-based
    doc.close()
    return page_texts


def get_page_images(source_id: str, images_dir: str) -> dict:
    """Scan the images directory and group image paths by page number.
    Returns {page_num: ["/images/source_id/p{page}_img{N}.png", ...]}
    """
    page_images = {}
    if not os.path.isdir(images_dir):
        return page_images
    for fname in sorted(os.listdir(images_dir)):
        if not fname.endswith('.png'):
            continue
        m = re.match(r'p(\d+)_img(\d+)\.png', fname)
        if m:
            page_num = int(m.group(1))
            img_path = f"/images/{source_id}/{fname}"
            if page_num not in page_images:
                page_images[page_num] = []
            page_images[page_num].append(img_path)
    return page_images


def process_file(json_path: str, pdf_path: str, source_id: str, images_base: str):
    """Process a single JSON+PDF pair."""
    print(f"\n{'='*60}")
    print(f"Processing: {source_id}")
    print(f"  JSON: {json_path}")
    print(f"  PDF:  {pdf_path}")

    # Load questions
    with open(json_path, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    images_dir = os.path.join(images_base, source_id)
    page_images = get_page_images(source_id, images_dir)

    total_images_on_disk = sum(len(v) for v in page_images.values())
    print(f"  Total images on disk: {total_images_on_disk}")

    # Collect all currently linked primary imageUrls
    linked_primary = set()
    for q in questions:
        if q.get('imageUrl'):
            linked_primary.add(q['imageUrl'])
    print(f"  Already linked as primary imageUrl: {len(linked_primary)}")

    # Build unlinked images per page
    unlinked_per_page = {}
    for page_num, imgs in page_images.items():
        unlinked = [img for img in imgs if img not in linked_primary]
        if unlinked:
            unlinked_per_page[page_num] = unlinked

    total_unlinked = sum(len(v) for v in unlinked_per_page.values())
    print(f"  Unlinked images to assign: {total_unlinked}")

    if total_unlinked == 0:
        print("  Nothing to do.")
        return 0

    # Extract per-page text from PDF
    page_texts = extract_page_texts(pdf_path)

    # Build normalized question fingerprints
    q_fingerprints = []
    for q in questions:
        fp = normalize(q['question'], 8)
        q_fingerprints.append(fp)

    # Build normalized page text fingerprints (full text, for substring matching)
    page_norm = {}
    for pnum, text in page_texts.items():
        page_norm[pnum] = normalize(text, 9999)  # full text normalized

    # For each page with unlinked images, try to match a question
    assigned_count = 0
    assigned_to_questions = set()

    # Also build a mapping: page -> which question IDs were found on that page
    page_to_qidx = {}
    for pnum in sorted(page_texts.keys()):
        norm_page = page_norm.get(pnum, '')
        if not norm_page:
            continue
        for qidx, fp in enumerate(q_fingerprints):
            if fp and fp in norm_page:
                if pnum not in page_to_qidx:
                    page_to_qidx[pnum] = []
                page_to_qidx[pnum].append(qidx)

    # Now assign unlinked images
    for pnum in sorted(unlinked_per_page.keys()):
        imgs = unlinked_per_page[pnum]

        # Try to find which question is on this page
        matched_qidx = None

        if pnum in page_to_qidx and page_to_qidx[pnum]:
            # Use the LAST question found on this page (most likely the one the image belongs to)
            matched_qidx = page_to_qidx[pnum][-1]
        else:
            # Fallback: try the previous page's last question
            prev = pnum - 1
            if prev in page_to_qidx and page_to_qidx[prev]:
                matched_qidx = page_to_qidx[prev][-1]

        if matched_qidx is not None:
            q = questions[matched_qidx]
            if 'imageUrls' not in q or q['imageUrls'] is None:
                q['imageUrls'] = []
            for img in imgs:
                if img not in q['imageUrls']:
                    q['imageUrls'].append(img)
                    assigned_count += 1
            assigned_to_questions.add(matched_qidx)
        else:
            # Try 2 pages back as well
            prev2 = pnum - 2
            if prev2 in page_to_qidx and page_to_qidx[prev2]:
                matched_qidx = page_to_qidx[prev2][-1]
                q = questions[matched_qidx]
                if 'imageUrls' not in q or q['imageUrls'] is None:
                    q['imageUrls'] = []
                for img in imgs:
                    if img not in q['imageUrls']:
                        q['imageUrls'].append(img)
                        assigned_count += 1
                assigned_to_questions.add(matched_qidx)

    print(f"  Assigned {assigned_count} images to {len(assigned_to_questions)} questions")

    # Remove empty imageUrls arrays (cleanup)
    for q in questions:
        if 'imageUrls' in q and (not q['imageUrls'] or q['imageUrls'] is None):
            del q['imageUrls']

    # Save
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {json_path}")

    return assigned_count


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    data_dir = os.path.join(project_dir, 'public', 'data')
    images_base = os.path.join(project_dir, 'public', 'images')

    # OphthoQ file mappings: json_name -> pdf_pattern
    MAPPINGS = [
        {"json": "cornea-oq.json",        "pdf": "2 - Cornea Ophtha.pdf",                "source_id": "cornea-oq"},
        {"json": "retina-oq.json",         "pdf": "7 - Retina - OQ.pdf",                  "source_id": "retina-oq"},
        {"json": "uveitis-oq.json",        "pdf": "5 - Uveitis OQ.pdf",                   "source_id": "uveitis-oq"},
        {"json": "neuro-oq.json",          "pdf": "8 - neuro OQ.pdf",                     "source_id": "neuro-oq"},
        {"json": "pedia-hy-oq.json",       "pdf": "5 - Pedia High Yield Questions .pdf",  "source_id": "pedia-hy-oq"},
        {"json": "fundamentals-oq.json",   "pdf": "1 - Fundamentals - OphthoQ.pdf",       "source_id": "fundamentals-oq"},
    ]

    grand_total = 0

    for m in MAPPINGS:
        json_path = os.path.join(data_dir, m["json"])
        pdf_path = os.path.join(project_dir, m["pdf"])

        if not os.path.exists(json_path):
            print(f"  SKIP: {m['json']} not found")
            continue
        if not os.path.exists(pdf_path):
            print(f"  SKIP: {m['pdf']} not found")
            continue

        count = process_file(json_path, pdf_path, m["source_id"], images_base)
        grand_total += count

    print(f"\n{'='*60}")
    print(f"GRAND TOTAL: {grand_total} secondary images linked")


if __name__ == "__main__":
    main()
