#!/usr/bin/env python3
"""
Turn the page-by-page vision extractions into published banks.

`parse_promotion.py` reads the PDF's text layer and anchors on runs of lettered
options.  Where a recall was pasted in as a screenshot -- stem and choices
inside an image, only "Answer: D" as text -- it has nothing to anchor on and
emits nothing.  Those pages were read directly instead; this merges the result.

Provenance is carried into every record rather than flattened away, because
these keys did not all come from the same place:

  keyFrom "text"            the compiler wrote the answer out
          "marked_in_image" only the exam screenshot shows which choice is right
          "both"            the two agree
  sourceHint                what the compiler wrote where an answer should be
                            ("?", "E", "D ???") when they were not sure
  authoredDistractors       the compiler recorded only the correct answer, so
                            the wrong options were written for this bank
  visionRead                read from the page image, not the text layer

Every vision-read question also carries a scan of its source page, since the
page is the evidence for both the stem and the key.

Usage:  python scripts/merge_vision.py [--year 2020] [--dry-run]
"""

import argparse
import collections
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

DATA = os.path.join(ROOT, "public", "data")
BATCHES = os.path.join(ROOT, "scripts", "vision", "pages")
SCAN_DIR = os.path.join(ROOT, "public", "images", "promotion-pages")
SCAN_WEB = "/images/promotion-pages"
SCAN_ZOOM = 2.0


def load_batches():
    """Every page record on disk, newest file wins if a page is repeated."""
    pages = {}
    for path in sorted(glob.glob(os.path.join(BATCHES, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            for rec in json.load(fh):
                pages[rec["page"]] = rec
    return pages


def page_context():
    """Subspecialty in force on each page, from the parser's own classifier."""
    import fitz
    import parse_promotion as P

    doc = fitz.open(P.PDF)
    subs, current = {}, None
    for i in range(doc.page_count):
        for ln in P.classify(P.extract_lines(doc, i)):
            if ln.kind == "subspec":
                current = ln.key
        subs[i + 1] = current or "Miscellaneous"
    return subs


def render_scan(page):
    """One JPEG per contributing page. The page is the evidence, so it ships."""
    import fitz
    import parse_promotion as P

    os.makedirs(SCAN_DIR, exist_ok=True)
    out = os.path.join(SCAN_DIR, f"page_{page:03d}.jpg")
    if not os.path.exists(out):
        doc = fitz.open(P.PDF)
        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(SCAN_ZOOM, SCAN_ZOOM))
        pix.save(out, jpg_quality=72)
    return f"{SCAN_WEB}/page_{page:03d}.jpg"


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


# Words that carry no identity in a clinical stem, so they are ignored when
# deciding whether two records are the same recall.
STOP = set("""a an the of to in on at with and or is are was were for from what which
following most likely patient patients this that he she his her him you your it its
has have had would will can could does do after before there they their""".split())


# The compiler writes in abbreviations and the vision pass writes them out, so
# "prevents RD" and "prevents retinal detachment" have no words in common at all.
# Collapsing the long forms back down puts both sides in the same vocabulary.
ABBREV = [
    (r"\bcystoid macular (?:oe|e)dema\b", "cme"),
    (r"\bdiabetic macular (?:oe|e)dema\b", "dme"),
    (r"\bposterior subcapsular cataract\b", "psc"),
    (r"\bretinal detachment\b", "rd"),
    (r"\bintraocular pressure\b", "iop"),
    (r"\bintraocular lens\b", "iol"),
    (r"\bphacoemulsification\b", "phaco"),
    (r"\bnon[- ]arteritic anterior ischemic optic neuropathy\b", "naion"),
    (r"\banterior ischemic optic neuropathy\b", "aion"),
    (r"\bposterior ischemic optic neuropathy\b", "pion"),
    (r"\binternuclear ophthalmoplegia\b", "ino"),
    (r"\bvisual field\b", "vf"),
    (r"\bvisual acuity\b", "va"),
    (r"\bglaucoma drainage (?:implant|device)\b", "gdi"),
    (r"\bmedial longitudinal fasciculus\b", "mlf"),
    (r"\bprimary acquired melanosis\b", "pam"),
    (r"\bthyroid[- ]associated orbitopathy\b", "tao"),
    (r"\bextraocular\b", "eom"),
    (r"\b(?:oe|e)dema\b", "edema"),
    (r"\bh(?:ae|e)morrhage\b", "hemorrhage"),
]


def words(text):
    t = (text or "").lower()
    for pattern, short in ABBREV:
        t = re.sub(pattern, short, t)
    return {w for w in re.findall(r"[a-z0-9]+", t) if w not in STOP and len(w) > 2}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def same_recall(a, b, page_gap=1, option_hit=0.45, option_share=0.5,
                stem=0.5, stem_floor=0.35):
    """
    Is this the same recall, recorded twice?

    Comparing stems verbatim finds almost none of the overlaps, because the
    vision pass rewrites the compiler's shorthand into proper prose -- it missed
    20 of 24 on the first 2021 run. Neither signal works alone:

      * Options alone over-match. Generic lists -- lobes, muscles, percentages
        -- repeat across unrelated questions. Page 261 asks where a field defect
        localises and what unformed hallucinations mean, and both offer the same
        four lobes.
      * Stems alone under-match, and options often cannot rescue them, because
        the compiler writes PAS, NVG, CME, "Staph", "LAISK" where this pass
        writes them out in full.

    So a close stem carries on its own, and a weaker stem needs the choices to
    agree as well. Both are measured on the same page, since a recall sits where
    it sits.
    """
    pa, pb = a.get("pdfPage") or 0, b.get("pdfPage") or 0
    if abs(pa - pb) > page_gap:
        return False

    qa, qb = words(a.get("question")), words(b.get("question"))
    stem_score = jaccard(qa, qb)

    # A close stem is enough on its own. It has to be, because the option lists
    # rarely line up word for word: the compiler writes PAS, NVG, CME, Staph,
    # "LAISK", while the vision pass writes them out in full.
    if stem_score >= stem:
        return True

    oa = [words(v) for v in a.get("options", {}).values() if words(v)]
    ob = [words(v) for v in b.get("options", {}).values() if words(v)]
    if len(oa) >= 2 and len(ob) >= 2:
        shared = sum(1 for x in oa if any(jaccard(x, y) >= option_hit for y in ob))
        # Matching choices alone are not enough either. Generic option lists --
        # lobes, muscles, percentages -- repeat across unrelated questions: page
        # 261 asks where a field defect localises and what unformed
        # hallucinations mean, and both offer the same four lobes. So the stems
        # still have to resemble each other, just less closely.
        return (shared / min(len(oa), len(ob)) >= option_share
                and stem_score >= stem_floor)

    return False


def supersede_rules(pages):
    """
    Recalls the vision pass judged duplicates of something it published from a
    different page, and so did not re-record. Matching cannot see these: the
    pages are far apart and the compiler's shorthand shares almost no wording
    with the full version. They are named explicitly in the batch instead.
    """
    rules = []
    for rec in pages.values():
        for rule in rec.get("supersedes", []):
            rules.append((rule["page"], rule["stemStartsWith"].lower()))
    return rules


def build(pages, subs):
    by_year = collections.defaultdict(list)
    for page in sorted(pages):
        rec = pages[page]
        for q in rec["questions"]:
            year = q.get("year") or rec["year"]
            item = {
                "id": 0,
                "source": f"promotion-{year}",
                "question": q["stem"],
                "options": q["options"],
                "correctAnswer": q["answer"],
                "year": year,
                "subspecialty": q.get("subspecialty") or subs.get(page, "Miscellaneous"),
                "pdfPage": page,
                "visionRead": True,
                "keyFrom": q["answerSource"],
                "pageScanUrl": render_scan(page),
            }
            if q.get("explanation"):
                item["explanation"] = q["explanation"]
            if q.get("reference"):
                item["explanation"] = (item.get("explanation", "") +
                                       f"  Reference: {q['reference']}").strip()
            if q.get("authoredDistractors"):
                item["authoredDistractors"] = True
            if q.get("sourceAnswerText") is not None:
                # An empty string is meaningful: the compiler left it blank.
                item["sourceHint"] = q["sourceAnswerText"]
            # Notes are written to add to the panel's own provenance line, not
            # to restate it, so they ship as recorded.
            if q.get("compilerNote"):
                item["sourceNote"] = q["compilerNote"]
            by_year[year].append(item)
    return by_year


def merge_into_bank(year, fresh, dry, rules=()):
    """Add to an existing bank if the parser already built one, else create it."""
    path = os.path.join(DATA, f"promotion-{year}.json")
    existing = []
    if os.path.exists(path):
        existing = json.load(open(path, encoding="utf-8"))

    # Where the vision pass re-read a recall the parser had already published,
    # the vision record wins: it carries the exam's real options rather than the
    # compiler's shorthand, states where its key came from, and ships a scan of
    # the source page.
    # A recall the compiler wrote down twice, pages apart, is still one recall.
    # Page proximity is dropped for that sweep and the thresholds tightened to
    # compensate, since without the page as evidence a loose match is a merge of
    # two genuinely different questions.
    def matches(q):
        for page, prefix in rules:
            if q.get("pdfPage") == page and q["question"].lower().startswith(prefix):
                return q                       # named explicitly in the batch
        return (next((f for f in fresh if same_recall(q, f)), None)
                or next((f for f in fresh if same_recall(
                    q, f, page_gap=10 ** 6, option_hit=0.6,
                    option_share=0.75, stem=0.65, stem_floor=0.5)), None))

    kept, replaced = [], []
    for q in existing:
        match = matches(q)
        if match:
            replaced.append((q, match))
        else:
            kept.append(q)

    # And guard against the vision pass itself recording one recall twice.
    added = []
    for q in fresh:
        if not any(same_recall(q, a) for a in added):
            added.append(q)
    dupes = len(fresh) - len(added)

    merged = kept + added
    merged.sort(key=lambda q: (q.get("pdfPage") or 0, q["question"][:40]))
    for i, q in enumerate(merged, 1):
        q["id"] = i
        q["source"] = f"promotion-{year}"

    if not dry:
        with io.open(path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False, indent=1)
    return existing, added, dupes, replaced, merged


def register(year, count, dry):
    path = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(path, encoding="utf-8"))
    bank = f"promotion-{year}"
    sets = [s for s in manifest["questionSets"] if s["id"] != bank]
    sets.append({
        "id": bank,
        "name": f"Promotion {year}",
        "description": f"{count} recalls from the {year} promotion exam.",
        "file": f"{bank}.json",
        "questionCount": count,
        "category": "promotion",
        "source": "Promotion",
    })
    sets.sort(key=lambda s: s["id"])
    manifest["questionSets"] = sets
    if not dry:
        with io.open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", action="append", help="only merge these years")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pages = load_batches()
    rules = supersede_rules(pages)
    subs = page_context()
    by_year = build(pages, subs)

    print(f"pages read: {len(pages)}   questions extracted: "
          f"{sum(len(v) for v in by_year.values())}")
    for year in sorted(by_year, reverse=True):
        print(f"    {year}: {len(by_year[year])}")

    targets = args.year or sorted(by_year)
    print()
    for year in sorted(targets, reverse=True):
        if year not in by_year:
            print(f"  {year}: nothing extracted yet")
            continue
        before, added, dupes, replaced, merged = merge_into_bank(
            year, by_year[year], args.dry_run, rules)
        register(year, len(merged), args.dry_run)
        print(f"  promotion-{year}: {len(before)} existing + {len(added)} read "
              f"= {len(merged)}")
        if replaced:
            print(f"      superseded the parser's shorthand for {len(replaced)} of them")
        if dupes:
            print(f"      {dupes} recall(s) recorded twice by the vision pass, collapsed")
        keyed = collections.Counter(q.get("keyFrom") for q in added)
        unsure = sum(1 for q in added if q.get("sourceHint") not in (None, ""))
        blank = sum(1 for q in added if q.get("sourceHint") == "")
        authored = sum(1 for q in added if q.get("authoredDistractors"))
        print(f"      key from: {dict(keyed)}")
        print(f"      compiler was unsure of the key: {unsure}   left it blank: {blank}")
        print(f"      distractors written for this bank: {authored}")

    if args.dry_run:
        print("\ndry run: nothing written")


if __name__ == "__main__":
    main()
