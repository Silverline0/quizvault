#!/usr/bin/env python3
"""
Batch parser for ALL BCSC Self Assessment PDFs.
Reuses the V3 anchor-based logic from parse_pdf_v3.py.
Downloads AAO images ONCE during parsing and saves them locally.
"""

import json
import re
import sys
import os
import glob
import urllib.request
import ssl
import time


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF."""
    import fitz
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def download_image(url: str, save_path: str) -> bool:
    """Download an image from URL and save locally. Returns True on success."""
    if os.path.exists(save_path):
        return True  # Already downloaded
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = resp.read()
            if len(data) < 100:  # Too small to be a real image
                return False
            with open(save_path, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        print(f"      [WARN] Failed to download image: {e}")
        return False


def extract_and_download_images(lines: list[str], source_id: str) -> dict:
    """
    Find all AAO image URLs in the text, download them once,
    and return a mapping of URL -> local path.
    """
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    images_dir = os.path.join(project_dir, "public", "images", source_id)
    os.makedirs(images_dir, exist_ok=True)

    url_map = {}  # aao_url -> local_web_path
    img_count = 0

    # Collect all unique image URLs
    urls_found = []
    for line in lines:
        # Match AAO image URLs (may be split across lines, so also catch partial)
        m = re.search(r'(https?://qas\.aao\.org/full/image\.axd\?[^\s\)]+)', line)
        if m:
            url = m.group(1).rstrip(')')
            if url not in url_map:
                urls_found.append(url)
                url_map[url] = None  # placeholder

    print(f"    Found {len(urls_found)} unique image URLs")

    for idx, url in enumerate(urls_found):
        # Extract image ID from URL for filename
        id_match = re.search(r'id=([a-f0-9\-]+)', url)
        if id_match:
            img_id = id_match.group(1)[:12]  # First 12 chars of UUID
        else:
            img_id = f"img{idx + 1}"

        filename = f"{img_id}.png"
        save_path = os.path.join(images_dir, filename)
        local_web_path = f"/images/{source_id}/{filename}"

        if download_image(url, save_path):
            url_map[url] = local_web_path
            img_count += 1
        else:
            url_map[url] = None

        # Small delay to be polite to AAO servers
        if idx < len(urls_found) - 1:
            time.sleep(0.2)

    print(f"    Downloaded {img_count}/{len(urls_found)} images")
    return url_map


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


def find_letter_anchors(lines):
    anchors = []
    n = len(lines)
    for i in range(n - 1):
        line = lines[i].strip()
        m = re.match(r'^([A-E])\.\s*$', line)
        if not m:
            continue
        letter = m.group(1)
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
        anchors.append((i, letter, pct, is_correct))
    return anchors


def group_into_option_sets(anchors):
    if not anchors:
        return []
    sets = []
    current_set = [anchors[0]]
    for k in range(1, len(anchors)):
        prev_line, prev_letter, _, _ = anchors[k - 1]
        curr_line, curr_letter, _, _ = anchors[k]
        gap = curr_line - prev_line
        if curr_letter <= prev_letter and gap > 3:
            sets.append(current_set)
            current_set = [anchors[k]]
        elif gap > 40:
            sets.append(current_set)
            current_set = [anchors[k]]
        else:
            current_set.append(anchors[k])
    if current_set:
        sets.append(current_set)
    return sets


def extract_option_text(lines, anchor_line, prev_boundary):
    parts = []
    i = anchor_line - 1
    while i >= prev_boundary:
        line = lines[i].strip()
        if not line:
            i -= 1
            continue
        if is_noise(line):
            break
        if line.startswith('(https://') or re.match(r'^id=[a-f0-9]', line):
            break
        if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}', line):
            break
        if is_question_header(line):
            break
        if line == 'Answer':
            break
        if re.match(r'^\d+%', line):
            break
        if re.match(r'^[A-E]\.\s*$', line):
            break
        parts.insert(0, line)
        i -= 1
    text = ' '.join(parts)
    text = re.sub(r'[\ue000-\uf8ff]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_image_urls_from_range(lines, start, end, url_map=None):
    """Extract image URLs from a line range, mapped to local paths."""
    local_paths = []
    for i in range(start, min(end, len(lines))):
        line = lines[i].strip()
        m = re.search(r'\(?(https?://qas\.aao\.org/full/image\.axd\?[^\s\)]+)', line)
        if m:
            url = m.group(1).rstrip(')')
            if url_map and url in url_map and url_map[url]:
                local_paths.append(url_map[url])
            else:
                local_paths.append(None)
    return [p for p in local_paths if p]


def build_option_set_data(lines, option_set):
    options = {}
    correct_answer = None
    stats = {}
    for idx, (anchor_line, letter, pct, is_correct) in enumerate(option_set):
        stats[letter] = pct
        if is_correct:
            correct_answer = letter
        if idx == 0:
            prev_boundary = max(0, anchor_line - 10)
        else:
            prev_anchor_line = option_set[idx - 1][0]
            prev_boundary = prev_anchor_line + 2
            if prev_boundary < len(lines) and lines[prev_boundary].strip() == 'Answer':
                prev_boundary += 1
        opt_text = extract_option_text(lines, anchor_line, prev_boundary)
        if opt_text:
            options[letter] = opt_text

    # Explanation
    last_anchor = option_set[-1]
    expl_start = last_anchor[0] + 2
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
        if re.match(r'^[A-E]\.\s*$', sl):
            if k + 1 < len(lines) and re.match(r'^\d+%', lines[k + 1].strip()):
                break
        expl_parts.append(sl)
    explanation = ' '.join(expl_parts)
    explanation = re.sub(r'\s+', ' ', explanation).strip()

    # Image URLs near the option set (will be filled by caller with url_map)
    block_start = max(0, option_set[0][0] - 15)
    block_end = min(len(lines), last_anchor[0] + 5)
    image_urls = extract_image_urls_from_range(lines, block_start, block_end, None)

    return options, correct_answer, dict(sorted(stats.items())), explanation, image_urls


def parse_bcsc_pdf(pdf_path: str, source_id: str) -> list:
    """Parse a single BCSC PDF and return list of question dicts."""
    print(f"  Extracting text from: {os.path.basename(pdf_path)}")
    text = extract_text_from_pdf(pdf_path)
    lines = text.split('\n')
    print(f"    {len(lines)} lines")

    # Download all AAO images locally
    print("  Downloading images...")
    url_map = extract_and_download_images(lines, source_id)

    headers = find_question_headers(lines)
    seen_nums = set()
    unique_headers = []
    for h in headers:
        if h[1] not in seen_nums:
            seen_nums.add(h[1])
            unique_headers.append(h)
    headers = unique_headers
    print(f"    {len(headers)} unique question headers")

    anchors = find_letter_anchors(lines)
    option_sets = group_into_option_sets(anchors)
    option_sets = [s for s in option_sets if len(s) >= 2]
    print(f"    {len(option_sets)} option sets")

    # Scan for image URLs near question headers, using local downloaded paths
    header_image_map = {}
    for idx, (header_end, q_num, _) in enumerate(headers):
        search_start = max(0, header_end - 5)
        next_start = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        search_end = min(len(lines), next_start + 30)
        img_paths = extract_image_urls_from_range(lines, search_start, search_end, url_map)
        if img_paths:
            header_image_map[q_num] = img_paths[0]

    option_sets_data = []
    for oset in option_sets:
        data = build_option_set_data(lines, oset)
        option_sets_data.append(data)

    headers_sorted = sorted(headers, key=lambda h: h[1])
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
            "imageUrl": header_image_map.get(q_num, None),
        }
        if idx < len(option_sets_data):
            opts, correct, stats, expl, img_urls = option_sets_data[idx]
            q["options"] = dict(sorted(opts.items()))
            q["correctAnswer"] = correct
            q["respondentStats"] = stats if stats else None
            q["explanation"] = expl
            if img_urls and not q["imageUrl"]:
                q["imageUrl"] = img_urls[0]

        # Clean options
        for k in list(q["options"].keys()):
            text = q["options"][k]
            text = re.sub(r'[\ue000-\uf8ff]', '', text)
            # Remove URL/GUID fragments
            text = re.sub(r'^.*?[a-f0-9]{6,}[&\w=]*\)\s*', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                q["options"][k] = text
            else:
                del q["options"][k]

        if len(q["options"]) >= 2 and len(q["question"]) > 10:
            questions.append(q)

    # Deduplicate
    seen = set()
    unique = []
    for q in questions:
        if q["id"] not in seen:
            seen.add(q["id"])
            unique.append(q)

    return sorted(unique, key=lambda q: q["id"])


# ── Batch configuration ────────────────────────────────────────────

BCSC_FILES = [
    {"pattern": "Pediatric*BCSC*Self*Assessment*", "source_id": "pediatric-bcsc",
     "name": "Pediatric BCSC", "category": "pediatrics"},
    {"pattern": "Cornea*BCSC*Self*Assessment*", "source_id": "cornea-bcsc",
     "name": "Cornea BCSC", "category": "cornea"},
    {"pattern": "Glaucoma*BCSC*Self*Assessment*", "source_id": "glaucoma-bcsc",
     "name": "Glaucoma BCSC", "category": "glaucoma"},
    {"pattern": "Neuro*BCSC*Self*Assessment*", "source_id": "neuro-bcsc",
     "name": "Neuro-Ophthalmology BCSC", "category": "neuro"},
    {"pattern": "Oculoplastics*BCSC*Self*Assessment*", "source_id": "oculoplastics-bcsc",
     "name": "Oculoplastics BCSC", "category": "oculoplastics"},
    {"pattern": "Optics*BCSC*Self*Assessment*", "source_id": "optics-bcsc",
     "name": "Optics BCSC", "category": "optics"},
    {"pattern": "Retina*BCSC*Self*Assessment*", "source_id": "retina-bcsc",
     "name": "Retina BCSC", "category": "retina"},
    {"pattern": "UVEITIS*BCSC*Self*Assessment*", "source_id": "uveitis-bcsc",
     "name": "Uveitis BCSC", "category": "uveitis"},
]


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    output_dir = os.path.join(project_dir, "public", "data")
    os.makedirs(output_dir, exist_ok=True)

    results = []

    for cfg in BCSC_FILES:
        matches = glob.glob(os.path.join(project_dir, cfg["pattern"] + ".pdf"))
        if not matches:
            print(f"  SKIP: No file matching '{cfg['pattern']}'")
            continue

        pdf_path = matches[0]
        print(f"\n{'='*60}")
        print(f"Parsing: {cfg['name']} ({cfg['source_id']})")
        print(f"  File: {os.path.basename(pdf_path)}")

        questions = parse_bcsc_pdf(pdf_path, cfg["source_id"])

        with_correct = sum(1 for q in questions if q["correctAnswer"])
        with_4opts = sum(1 for q in questions if len(q["options"]) >= 4)
        with_images = sum(1 for q in questions if q.get("imageUrl"))

        print(f"  Result: {len(questions)} questions")
        print(f"    Correct answers: {with_correct}")
        print(f"    4+ options: {with_4opts}")
        print(f"    With images: {with_images}")

        json_path = os.path.join(output_dir, f"{cfg['source_id']}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        results.append({
            "id": cfg["source_id"],
            "name": cfg["name"],
            "category": cfg["category"],
            "file": f"{cfg['source_id']}.json",
            "questionCount": len(questions),
            "source": "BCSC",
        })

    # Print summary
    print(f"\n{'='*60}")
    print("BCSC BATCH SUMMARY")
    total = sum(r["questionCount"] for r in results)
    for r in results:
        print(f"  {r['name']}: {r['questionCount']} questions")
    print(f"  TOTAL: {total} questions across {len(results)} sets")

    # Save results metadata for manifest builder
    meta_path = os.path.join(output_dir, "_bcsc_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nMetadata: {meta_path}")


if __name__ == "__main__":
    main()
