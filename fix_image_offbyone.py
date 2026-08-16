#!/usr/bin/env python3
"""
Fix off-by-one image linking in quiz JSON files.

In interleaved PDF layouts, Q_N's image sometimes gets assigned to Q_N+1
because the image appears on the same page as Q_N+1's header text.

This script:
1. For each question with imageUrl/imageUrls, extracts the page number
2. Opens the PDF, gets the text of that page
3. Checks whether the CURRENT or PREVIOUS question text appears on the page
4. Reassigns images to the previous question when appropriate
"""

import fitz
import json
import re
import unicodedata
from pathlib import Path

BASE_DIR = Path("C:/Users/s3udi/projects/Quizzes")
DATA_DIR = BASE_DIR / "public" / "data"

# Mapping: json filename -> PDF filename
FILE_MAP = {
    "pediatric-bcsc.json": "Pediatric  BCSC Self Assessment\u2026.pdf",
    "cornea-bcsc.json": "Cornea  BCSC Self Assessment.pdf",
    "glaucoma-bcsc.json": "Glaucoma  BCSC Self Assessment.pdf",
    "neuro-bcsc.json": "Neuro  BCSC Self Assessment Program.pdf",
    "oculoplastics-bcsc.json": "Oculoplastics  BCSC Self Assessment AAO.pdf",
    "retina-bcsc.json": "Retina  BCSC Self Assessment.pdf",
    "uveitis-bcsc.json": "UVEITIS  BCSC Self Assessment.pdf",
    "optics-bcsc.json": "Optics  BCSC Self Assessment AAO.pdf",
    "fundamentals-oq.json": "1 - Fundamentals - OphthoQ.pdf",
    "cornea-oq.json": "2 - Cornea Ophtha.pdf",
    "lens-cataract-oq.json": "3- Lens and Cataract OphthoQ.pdf",
    "pedia-hy-oq.json": "5 - Pedia High Yield Questions .pdf",
    "uveitis-oq.json": "5 - Uveitis OQ.pdf",
    "pedia-nhy-oq.json": "6 - Pedia Non-High Yield Questions .pdf",
    "retina-oq.json": "7 - Retina - OQ.pdf",
    "neuro-oq.json": "8 - neuro OQ.pdf",
}


def normalize(text):
    """Normalize text for fuzzy matching: NFKD, lowercase, strip non-alnum."""
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_question_snippet(question_text, n_words=8):
    """Get first N words of question, normalized."""
    words = question_text.split()[:n_words]
    return normalize(" ".join(words))


def extract_page_num(image_path):
    """Extract page number from image filename like p123_img1.png."""
    m = re.search(r"p(\d+)_img", image_path)
    if m:
        return int(m.group(1))
    return None


def check_image_ownership(doc, page_num, current_q, prev_q):
    """
    Determine if an image on page_num belongs to current_q or prev_q.

    Returns:
        'current' - image correctly belongs to current question
        'previous' - image should be reassigned to previous question
        'keep' - cannot determine, keep current assignment
    """
    if page_num < 1 or page_num > len(doc):
        return "keep"

    page = doc[page_num - 1]
    ptext = normalize(page.get_text())

    cur_snippet = get_question_snippet(current_q["question"])
    cur_on_page = cur_snippet in ptext

    prev_on_page = False
    if prev_q:
        prev_snippet = get_question_snippet(prev_q["question"])
        prev_on_page = prev_snippet in ptext

    if cur_on_page and not prev_on_page:
        # Only current question on page - correct assignment
        return "current"

    if not cur_on_page and prev_on_page:
        # Only previous question on page - off-by-one!
        return "previous"

    if cur_on_page and prev_on_page:
        # Both on page - check text position
        cur_pos = ptext.find(cur_snippet)
        prev_pos = ptext.find(prev_snippet)

        if prev_pos < cur_pos:
            # Previous question appears first on the page.
            # The image is between prev question content and current question header,
            # so it belongs to the previous question.
            return "previous"
        else:
            # Current question appears first (unusual but possible)
            return "current"

    # Neither found - cannot determine, keep as is
    return "keep"


def process_file(json_filename, pdf_filename):
    """Process a single JSON file, fixing image assignments."""
    json_path = DATA_DIR / json_filename
    pdf_path = BASE_DIR / pdf_filename

    if not json_path.exists():
        print(f"  SKIP: {json_filename} not found")
        return 0
    if not pdf_path.exists():
        print(f"  SKIP: {pdf_filename} not found")
        return 0

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    doc = fitz.open(str(pdf_path))
    qmap = {q["id"]: q for q in data}

    # Track images to move: list of (from_q_id, to_q_id, image_url, field)
    moves = []

    for q in data:
        prev_q = qmap.get(q["id"] - 1)

        # Check imageUrl
        if q.get("imageUrl"):
            page_num = extract_page_num(q["imageUrl"])
            if page_num:
                owner = check_image_ownership(doc, page_num, q, prev_q)
                if owner == "previous" and prev_q:
                    # Check if prev already has this exact image
                    prev_has = (prev_q.get("imageUrl") == q["imageUrl"]) or (
                        q["imageUrl"] in (prev_q.get("imageUrls") or [])
                    )
                    if not prev_has:
                        moves.append(
                            (q["id"], prev_q["id"], q["imageUrl"], "imageUrl")
                        )

        # Check imageUrls array
        if q.get("imageUrls"):
            for img_url in list(q["imageUrls"]):
                page_num = extract_page_num(img_url)
                if page_num:
                    owner = check_image_ownership(doc, page_num, q, prev_q)
                    if owner == "previous" and prev_q:
                        prev_has = (prev_q.get("imageUrl") == img_url) or (
                            img_url in (prev_q.get("imageUrls") or [])
                        )
                        if not prev_has:
                            moves.append(
                                (q["id"], prev_q["id"], img_url, "imageUrls")
                            )

    doc.close()

    # Apply moves
    reassigned = 0
    for from_id, to_id, img_url, field in moves:
        from_q = qmap[from_id]
        to_q = qmap[to_id]

        # Remove from source
        if field == "imageUrl":
            if from_q.get("imageUrl") == img_url:
                from_q["imageUrl"] = None
        elif field == "imageUrls":
            if from_q.get("imageUrls") and img_url in from_q["imageUrls"]:
                from_q["imageUrls"].remove(img_url)
                if not from_q["imageUrls"]:
                    from_q["imageUrls"] = None

        # Add to destination: prefer imageUrl slot if empty, else use imageUrls
        if to_q.get("imageUrl") is None:
            to_q["imageUrl"] = img_url
        else:
            if to_q.get("imageUrls") is None:
                to_q["imageUrls"] = []
            if img_url not in to_q["imageUrls"]:
                to_q["imageUrls"].append(img_url)

        reassigned += 1
        print(f"    Q{from_id} -> Q{to_id}: {img_url}")

    # Clean up: remove empty imageUrls arrays, set to None
    for q in data:
        if q.get("imageUrls") is not None and len(q.get("imageUrls", [])) == 0:
            q["imageUrls"] = None

    # Save if changes were made
    if reassigned > 0:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open(json_path, "a", encoding="utf-8") as f:
            f.write("\n")

    return reassigned


def main():
    print("=" * 60)
    print("Image Off-By-One Fix Script")
    print("=" * 60)

    total_reassigned = 0
    results = {}

    for json_file, pdf_file in FILE_MAP.items():
        print(f"\n{json_file}:")
        count = process_file(json_file, pdf_file)
        total_reassigned += count
        results[json_file] = count
        if count > 0:
            print(f"  -> Reassigned {count} images")
        else:
            print(f"  -> No changes needed")

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    for f, c in results.items():
        status = f"{c} reassigned" if c > 0 else "no changes"
        print(f"  {f}: {status}")
    print(f"\nTOTAL IMAGES REASSIGNED: {total_reassigned}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
