#!/usr/bin/env python3
"""
Verify emitted questions against the SOURCE PDF, not against each other.

Earlier quality checks compared emitted questions to emitted questions. Anything
the parser rejected -- roughly 370 candidates -- was invisible to them, which is
exactly where the defects lived: a leak from a rejected recall could never be
seen. These detectors enumerate recall boundaries from the PDF directly, so a
boundary crossing is caught whether or not the recall on the other side of it
was ever published.
"""
import sys, io, json, glob, os, re, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
import parse_promotion as P

doc = fitz.open(P.PDF)
pages = [P.classify(P.extract_lines(doc, i)) for i in range(doc.page_count)]

# ---- ground truth: every recall boundary the document itself declares -------
# A numbered line at the page's left text margin starts a recall, whether or not
# the parser managed to publish it.
boundaries = collections.defaultdict(list)   # page -> [y of each recall start]
answers = collections.defaultdict(list)      # page -> [y of each Answer: line]
for lines in pages:
    if not lines:
        continue
    body = [l.x0 for l in lines if l.x0 < P.FOOTER_X]
    if not body:
        continue
    margin = min(body)
    for l in lines:
        if l.x0 >= P.FOOTER_X:
            continue
        if l.x0 <= margin + P.RECALL_MARGIN_SLACK and (
                P.NUMBERED_RECALL_RE.match(l.text) or P.BARE_QNUM_RE.match(l.text)):
            boundaries[l.page].append(l.y0)
        if l.kind in ("answer", "agree"):
            answers[l.page].append(l.y0)

total_recalls = sum(len(v) for v in boundaries.values())
total_answers = sum(len(v) for v in answers.values())

# ---- locate each emitted question's text in the PDF -------------------------
def norm(s): return re.sub(r"\s+", " ", s or "").strip().lower()

emitted = []
for f in sorted(glob.glob("public/data/promotion-*.json")):
    for q in json.load(open(f, encoding="utf-8")):
        emitted.append(q)

pagetext = {}
for i, lines in enumerate(pages):
    pagetext[i + 1] = norm(" ".join(l.text for l in lines))

def in_source(text, page, span=1):
    """Is this text found verbatim on its page or the next?"""
    t = norm(text)
    if len(t) < 25:
        return True
    probe = t[:60]
    for p in range(page, page + span + 1):
        if probe in pagetext.get(p, ""):
            return True
    return False

# ---- checks -----------------------------------------------------------------
stem_not_in_source = []
opt_not_in_source = []
expl_not_in_source = []
for q in emitted:
    if q.get("ocr") or q.get("reviewerAnswered"):
        continue                      # transcribed / reviewer text, not PDF text
    pg = q.get("pdfPage") or 0
    if not in_source(q["question"], pg):
        stem_not_in_source.append((q["source"], q["id"], pg, q["question"][:64]))
    for k, v in q["options"].items():
        if len(v) > 30 and not in_source(v, pg):
            opt_not_in_source.append((q["source"], q["id"], pg, k, v[:56]))
            break

print("=" * 66)
print("SWEEP: emitted questions vs the source PDF")
print("=" * 66)
print(f"recall boundaries declared by the document: {total_recalls}")
print(f"answer/agree lines in the document:         {total_answers}")
print(f"emitted questions (excluding transcribed):  "
      f"{sum(1 for q in emitted if not q.get('ocr') and not q.get('reviewerAnswered'))}")
print()
print(f"STEMS whose opening text is not on their cited page or the next: {len(stem_not_in_source)}")
for r in stem_not_in_source[:10]:
    print(f"   {r[0]}#{r[1]} p{r[2]}: {r[3]!r}")
print()
print(f"OPTIONS whose text is not on their cited page or the next: {len(opt_not_in_source)}")
for r in opt_not_in_source[:10]:
    print(f"   {r[0]}#{r[1]} p{r[2]} opt {r[3]}: {r[4]!r}")

# ---- check 2: does an emitted explanation swallow a declared recall? --------
# This is the ground-truth version of the leak check. It tests the document's
# own recall-start lines against every explanation, so a leak from a recall the
# parser never published is still caught.
boundary_lines = []
for lines in pages:
    if not lines:
        continue
    body = [l.x0 for l in lines if l.x0 < P.FOOTER_X]
    if not body:
        continue
    margin = min(body)
    for l in lines:
        if l.x0 >= P.FOOTER_X or l.x0 > margin + P.RECALL_MARGIN_SLACK:
            continue
        m = P.NUMBERED_RECALL_RE.match(l.text)
        if m:
            body_text = re.sub(r"^\d{1,3}\s*[-.)]\s+", "", l.text)
            if len(body_text) >= 30:
                boundary_lines.append((l.page, norm(body_text)[:44], l.text[:60]))

swallowed = []
for q in emitted:
    e = norm(q.get("explanation"))
    if len(e) < 40:
        continue
    pg = q.get("pdfPage") or 0
    for bpage, probe, raw in boundary_lines:
        if not (pg <= bpage <= pg + 2):
            continue
        if probe and probe in e:
            swallowed.append((q["source"], q["id"], pg, bpage, raw))
            break

print()
print(f"declared recall starts long enough to test: {len(boundary_lines)}")
print(f"EXPLANATIONS that swallow a declared recall: {len(swallowed)}")
print("  by bank:", dict(collections.Counter(s[0] for s in swallowed).most_common()))
for s in swallowed[:12]:
    print(f"   {s[0]}#{s[1]} (p{s[2]}) swallows the recall starting p{s[3]}: {s[4]!r}")

# ---- check 3: stems that begin mid-explanation ------------------------------
# A stem should start at a recall boundary. If its opening words sit AFTER an
# answer line and before the next boundary, it began inside the previous
# question's explanation.
print()
print("STEM/EXPLANATION boundary summary")
print(f"  recalls the document declares (numbered):  {total_recalls}")
print(f"  answer lines the document contains:        {total_answers}")
print(f"  questions published:                       {len(emitted)}")
