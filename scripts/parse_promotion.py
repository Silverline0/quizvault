#!/usr/bin/env python3
"""
Parse "Promotion Exam ( 2025-2014).pdf" into QuizVault question-set JSON.

The document is a human-compiled 661-page recall bank spanning 12 exam years,
marked up on an iPad.  It mixes at least six question layouts, so the parser
works off geometry and font metadata rather than raw text order.

Architecture
------------
Questions are anchored on *option runs* -- maximal sequences of consecutive
choice lines -- rather than on question numbers.  Numbering in this document
restarts, skips, disappears entirely (2014/2017 sections) and sometimes gets
swallowed by a Word auto-list ("3. 32- patient can see ..."), but every real
question has a run of choices.  For each run the parser walks backwards for the
stem and forwards for the answer/explanation, which behaves uniformly across
all layouts.

Supporting mechanics
--------------------
* Handwriting removal: the iPad markup layer is embedded with Apple system
  fonts, which are always dot-prefixed (".SFUI-Regular_wdth_opsz1",
  ".SFArabic-Regular", ...).  Real document text never is, so dropping
  dot-prefixed spans strips the annotation noise deterministically.
* Images bind to questions by vertical position between stem anchors, never by
  sequential index -- index-based linking is what produced the off-by-one image
  bugs fixed in earlier commits.
* Emission is conservative: a candidate becomes a question only with a stem,
  >= 2 options and a resolvable answer.  Everything else lands in a reject log,
  so coverage is measured rather than assumed.
"""

import io
import json
import os
import re
import sys
import glob
import hashlib
import collections

import fitz  # PyMuPDF

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "Promotion Exam ( 2025-2014).pdf")
IMG_DIR = os.path.join(ROOT, "public", "images", "promotion")
DATA_DIR = os.path.join(ROOT, "public", "data")
REPORT_DIR = os.environ.get("PROMO_REPORT", os.path.join(ROOT, "scripts"))

# --------------------------------------------------------------------------
# Section map: (start_page, end_page, default_year) -- 1-based, inclusive.
# Boundaries come from the title/TOC pages inside the document.
# The 2018-2022 block is subspecialty-major with inline year subheaders, so it
# carries no default year and relies on those.
# --------------------------------------------------------------------------
SECTIONS = [
    (1, 40, "2025"),
    (41, 84, "2024"),
    (85, 120, "2023"),
    (121, 296, None),
    # 2017 and 2016 share a page: the "2016" header sits mid-way down page 397,
    # with 2017's numbering running unbroken up to it.  Splitting on a page
    # boundary stamped nine 2017 recalls as 2016, so this block carries no
    # default year and lets the inline header place them.
    (297, 448, None),
    (449, 542, "2015"),
    (543, 661, "2014"),
]

SUBSPECIALTIES = {
    "anterior segment": "Anterior Segment", "as": "Anterior Segment",
    "cornea": "Anterior Segment", "lens": "Anterior Segment",
    "retina": "Retina", "uveitis": "Uveitis", "glaucoma": "Glaucoma",
    "pediatrics": "Pediatrics", "pediatric": "Pediatrics",
    "peds": "Pediatrics", "pedia": "Pediatrics",
    "oculoplastic": "Oculoplastics", "oculoplastics": "Oculoplastics",
    "neuro-ophtha": "Neuro-Ophthalmology", "neuro ophtha": "Neuro-Ophthalmology",
    "neuroophtha": "Neuro-Ophthalmology", "neuro": "Neuro-Ophthalmology",
    "neuro-ophthalmology": "Neuro-Ophthalmology",
    "optics": "Optics", "pathology": "Pathology",
    "miscellaneous": "Miscellaneous", "misc": "Miscellaneous",
}

# --------------------------------------------------------------------------
# Text normalisation
# --------------------------------------------------------------------------
LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi",
    "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-",
    " ": " ", "​": "",
}

# Wingdings/Symbol bullets survive extraction as mojibake.  "3/4" is what the
# Wingdings list glyph becomes after "⁄" is normalised to "/", so it must
# be matched *after* normalisation.
BULLET_GLYPHS = ["3/4", "§", "à", "•", "○", "▪",
                 "■", "‣", "⁃", "", "", ""]

GARBAGE_RE = re.compile(r"[ɐ-˿̀-ͯ]{3,}")

# Apple Scribble does not only emit the dot-prefixed system fonts: it also drops
# recognised-ink islands in plain Helvetica ("E.im", "cniaI", an oversized
# x-with-overline used as a strike mark).  Every span in these two faces across
# all 661 pages is annotation or whitespace, so both are dropped wholesale.
ANNOTATION_FONTS = {"Helvetica", "HelveticaNeue"}

# Zero-width and control characters that carry no meaning but do break the
# option regexes: a stray U+2060 in front of "B. lateral geniculate" stopped
# that line being read as a choice at all, so the option was lost and leaked
# into the stem instead.
INVISIBLE_RE = re.compile(
    "[\x00-\x08\x0b-\x1f\xad\u180e\u200b-\u200f\u2060-\u2064\ufeff]")


# Part of the 2014 block was set with a subset font whose ligature slots decode
# to punctuation and digits: "ar=cle" (article), "la9ce" (lattice), "tu6s"
# (tufts), "cys$c" (cystic), "hEps://" (https://).
#
# These characters also occur legitimately, so the repair is token-aware:
#   * "=" is a query separator in "?origin=publication" -- left alone after ? or &
#   * digits are meaningful in UUIDs like "4d1c-8785-3022808e0c6d" -- a token
#     carrying more than one digit is data, not a mangled word.
SUBSET_SLOT = {"=": "ti", "$": "ti", "9": "tti", "6": "ft"}
SUBSET_IN_WORD = re.compile(r"(?<=[a-z])([=$96])(?=[a-z])")
SCHEME_FIX = re.compile(r"\bh[Ef]ps(?=://)")

# "ti" also degrades to a hyphen ("degenera-on", "re-nal").  Hyphens are real
# punctuation, so this runs only on the confirmed shapes and never on a genuine
# compound such as the "add-on" of an add-on IOL.
HYPHEN_TI_KEEP = {"add-on", "add-ons", "follow-on", "hands-on", "knock-on",
                  "run-on", "spin-on", "clip-on", "lock-on"}
HYPHEN_TI_ON = re.compile(r"\b[a-z]{3,}-ons?\b")
HYPHEN_TI_RETIN = re.compile(r"\bre-n(al|a|as|opathy|oschisis)\b")


def fix_subset_font(text):
    if not SUBSET_IN_WORD.search(text) and "hEps" not in text and "hfps" not in text:
        return text
    out = []
    for token in text.split(" "):
        token = SCHEME_FIX.sub("https", token)
        digits = sum(c.isdigit() for c in token)

        def slot(m):
            ch = m.group(1)
            if ch in "96" and digits > 1:
                return ch                      # UUID or numeric string
            if ch == "=" and ("?" in token or "&" in token):
                return ch                      # URL query parameter
            return SUBSET_SLOT[ch]

        out.append(SUBSET_IN_WORD.sub(slot, token))
    return " ".join(out)


def fix_hyphen_ti(text):
    def on_repl(m):
        word = m.group()
        return word if word.lower() in HYPHEN_TI_KEEP else word.replace("-", "ti")
    text = HYPHEN_TI_ON.sub(on_repl, text)
    return HYPHEN_TI_RETIN.sub(lambda m: "retin" + m.group(1), text)


def normalise(text):
    # A Greek beta set in an MS-Mincho fallback decodes to NUL; in this
    # document it is always the beta of "beta-blockers".
    text = text.replace("\x00-blocker", "beta-blocker")
    text = INVISIBLE_RE.sub("", text)
    for a, b in LIGATURES.items():
        text = text.replace(a, b)
    # The "ti" ligature decodes to a capital W on ~15 pages (opWc -> optic).
    # Only inside an otherwise all-lowercase word: CamelCase citations such as
    # "EyeWiki" are real text, not corruption.
    text = re.sub(r"\b[a-z]+W[a-z]+\b",
                  lambda m: m.group().replace("W", "ti"), text)
    # The "ff" ligature degrades to a backtick in a few 2025-section spans.
    text = re.sub(r"(?<=[A-Za-z])`(?=[a-z])", "ff", text)
    text = text.replace("⁄", "/")
    text = fix_subset_font(text)
    text = fix_hyphen_ti(text)
    # A Wingdings arrow survives mid-line, where the bullet stripper never sees it.
    if "à" in text[1:]:
        text = re.sub(r"\s*à\s*", " -> ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def is_garbage(line):
    if GARBAGE_RE.search(line):
        return True
    ascii_letters = sum(c.isalpha() and ord(c) < 128 for c in line)
    if len(line) > 12 and ascii_letters < len(line) * 0.35:
        # Keep genuine Arabic annotations out of the stem, they are marginalia.
        return True
    return False


# --------------------------------------------------------------------------
# Line model
# --------------------------------------------------------------------------
class Line:
    __slots__ = ("text", "page", "y0", "y1", "x0", "bold", "size", "kind", "key", "body")

    def __init__(self, text, page, y0, y1, x0, bold, size):
        self.text, self.page = text, page
        self.y0, self.y1, self.x0 = y0, y1, x0
        self.bold, self.size = bold, size
        self.kind = "text"
        self.key = None
        self.body = None

    def __repr__(self):
        return f"<p{self.page} y{self.y0:.0f} {self.kind}:{self.key} {self.text[:40]!r}>"


def extract_lines(doc, pno):
    """Clean, reading-ordered lines for one page with handwriting stripped."""
    page = doc[pno]
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for ln in block["lines"]:
            spans = [s for s in ln["spans"]
                     if not s["font"].startswith(".")
                     and s["font"] not in ANNOTATION_FONTS]
            if not spans:
                continue
            text = normalise("".join(s["text"] for s in spans))
            if not text or is_garbage(text):
                continue
            bold = any("Bold" in s["font"] for s in spans)
            out.append(Line(text, pno + 1, ln["bbox"][1], ln["bbox"][3],
                            ln["bbox"][0], bold, spans[0]["size"]))
    out.sort(key=lambda l: (round(l.y0, 1), l.x0))
    return out


# --------------------------------------------------------------------------
# Line classification
# --------------------------------------------------------------------------
LETTER_OPT_RE = re.compile(r"^([A-Ha-h])\s*[-.):]\s*(\S.*)$")
LETTER_BARE_RE = re.compile(r"^([A-Ha-h])\s*[-.):]\s*$")
NUM_LETTER_OPT_RE = re.compile(r"^\d{1,2}\s*[.)]\s*([A-Ha-h])\s*[-.):]\s*(\S.*)$")
NUM_OPT_RE = re.compile(r"^(\d{1,2})\s*[.)]\s+(\S.*)$")
QNUM_RE = re.compile(r"^(?:\d{1,2}\s*[.)]\s*)?(\d{1,3})\s*[-.)]\s*(.*)$")
ANSWER_RE = re.compile(r"^(?:Correct\s+)?(?:Answer|Ans|ANS)\b\s*[:.\-]?\s*(.*)$", re.I)
AGREE_RE = re.compile(r"^(Agree|Agreed|Disagree)\b\s*[:,.\-]?\s*(.*)$", re.I)
# These must be LABELS, not a word that happens to end a wrapped stem line:
# "...what is the most common explanation?" was being read as a label, which
# truncated the stem to nothing.
EXPL_RE = re.compile(r"^Explanation\s*(?:[:.\-]\s*(.*)|)$", re.I)
REF_RE = re.compile(r"^References?\s*(?:[:.\-]\s*(.*)|)$", re.I)
YEAR_RE = re.compile(r"^(?:##\s*)?(20\d\d)\s*[:.\-]?\s*$")
SEC_RE = re.compile(r"^##\s*(.+?)(?:\s*\.{3,}.*)?$")
TOC_RE = re.compile(r"\.{6,}\s*\d+\s*$")
PAGENUM_RE = re.compile(r"^\d{1,3}$")
INCOMPLETE_RE = re.compile(r"^\??\s*incomplete\s+q", re.I)
BARE_LETTER_RE = re.compile(r"^\(?([A-H])\)?\s*\.?$")
# A question number on a line of its own: the whole recall is a screenshot and
# Word dropped the list number at the inline image's baseline.
BARE_QNUM_RE = re.compile(r"^(\d{1,3})\s*[-.):]?\s*$")
# A numbered line carrying real text -- "22. Patient with late wave-like
# staining ...".  Recalls that preserve only one option form no option run, so
# the per-run explanation boundary never sees them and the previous question's
# explanation swallows them whole.  Indentation separates the two cases: a
# question number sits at the stem's own margin, a list item inside an
# explanation is indented past it.
NUMBERED_RECALL_RE = re.compile(r"^\d{1,3}\s*[-.)]\s+\S")
RECALL_MARGIN_SLACK = 6.0
PLACEHOLDER_RE = re.compile(r"^[\s.…?\-_*]*$")


def bullet_body(text):
    for g in BULLET_GLYPHS:
        if text.startswith(g):
            return text[len(g):].strip(" .-)•")
    return None


def subspec_of(text):
    t = re.sub(r"\s*\(.*\)$", "", text.strip().rstrip(":").strip()).lower()
    return SUBSPECIALTIES.get(t) if len(t) <= 30 else None


def classify(lines):
    """Tag each line with a kind; option lines also get key/body."""
    for ln in lines:
        t = ln.text.strip()
        if TOC_RE.search(t) or (PAGENUM_RE.match(t) and len(t) <= 3):
            ln.kind = "skip"
            continue
        m = YEAR_RE.match(t)
        if m:
            ln.kind, ln.key = "year", m.group(1)
            continue
        sm = SEC_RE.match(t)
        if sm and subspec_of(sm.group(1)):
            ln.kind, ln.key = "subspec", subspec_of(sm.group(1))
            continue
        s = subspec_of(t)
        if s and (ln.size >= 13 or t.endswith(":")):
            ln.kind, ln.key = "subspec", s
            continue
        if ANSWER_RE.match(t):
            ln.kind, ln.body = "answer", ANSWER_RE.match(t).group(1).strip()
            continue
        am = AGREE_RE.match(t)
        if am:
            ln.kind, ln.key, ln.body = "agree", am.group(1).lower(), am.group(2).strip()
            continue
        if EXPL_RE.match(t):
            ln.kind, ln.body = "expl", (EXPL_RE.match(t).group(1) or "").strip()
            continue
        if REF_RE.match(t):
            ln.kind, ln.body = "ref", (REF_RE.match(t).group(1) or "").strip()
            continue
        if INCOMPLETE_RE.match(t):
            ln.kind = "incomplete"
            continue

        m = NUM_LETTER_OPT_RE.match(t)
        if m:
            ln.kind, ln.key, ln.body = "opt", m.group(1).upper(), m.group(2).strip()
            continue
        m = LETTER_OPT_RE.match(t)
        if m:
            ln.kind, ln.key, ln.body = "opt", m.group(1).upper(), m.group(2).strip()
            continue
        m = LETTER_BARE_RE.match(t)
        if m:
            ln.kind, ln.key, ln.body = "opt", m.group(1).upper(), ""
            continue
        b = bullet_body(t)
        if b is not None:
            ln.kind, ln.key, ln.body = "bullet", None, b
            continue
        m = NUM_OPT_RE.match(t)
        if m and len(m.group(2)) < 110 and int(m.group(1)) <= 15:
            # Provisional only.  A "3. text" line is ambiguous between a
            # numbered choice and a question number; find_runs disambiguates
            # by looking at what follows.
            ln.kind, ln.key, ln.body = "numopt", int(m.group(1)), m.group(2).strip()
            continue
    return lines


def next_choice(lines, i):
    """Next option-ish line at or after i, skipping wrapped text."""
    for j in range(i, min(i + 4, len(lines))):
        if lines[j].kind in ("opt", "bullet", "numopt"):
            return lines[j]
        if lines[j].kind not in ("text", "skip"):
            return None
    return None


def is_star_marked(body):
    """
    A trailing "*" flags the correct choice in the 2015/2016 sections.  But the
    same character is also markdown emphasis ("*deep stromal neovascularization*")
    and an author's aside, so a body that both opens and closes with one is
    emphasis, not an answer key.
    """
    b = body.strip()
    if not b.endswith("*"):
        return False
    return not b.startswith("*")


def clean_star(body):
    """Drop marker and emphasis asterisks so neither leaks into the option text."""
    return body.strip().strip("*").strip()


# --------------------------------------------------------------------------
# Option-run detection
# --------------------------------------------------------------------------
def find_runs(lines):
    """
    Locate maximal runs of option lines.  Returns [(start_idx, end_idx, opts)]
    where opts is an OrderedDict key -> (body, starred).
    """
    runs = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if ln.kind not in ("opt", "bullet", "numopt"):
            i += 1
            continue

        # A numbered line only opens a run when the *next* choice is also a
        # numbered one continuing the sequence.  Otherwise it is a question
        # number ("3. child with oil droplet reflection ...") and the real run
        # begins at the lettered choice that follows.
        if ln.kind == "numopt":
            nxt = next_choice(lines, i + 1)
            if nxt is None or nxt.kind != "numopt" or nxt.key != ln.key + 1:
                i += 1
                continue

        style = ln.kind
        opts = collections.OrderedDict()
        start = i
        last_letter = None
        last_num = None
        last_line = None
        j = i
        gap = 0

        while j < n:
            cur = lines[j]
            if cur.kind == style or (style in ("bullet", "numopt") and cur.kind == "opt"):
                if cur.kind == "opt":
                    k = cur.key
                    if last_letter is not None and k <= last_letter:
                        break                       # keys must ascend
                    if last_letter is None and k not in ("A", "B"):
                        # A run starting at C+ is a continuation artefact only
                        # if nothing precedes it; treat as its own run.
                        pass
                    last_letter = k
                elif cur.kind == "numopt":
                    if last_num is not None and cur.key != last_num + 1:
                        break
                    last_num = cur.key
                    k = chr(ord("A") + len(opts))
                else:
                    k = chr(ord("A") + len(opts))
                body = cur.body or ""
                starred = is_star_marked(body)
                body = clean_star(body)
                opts[k] = [body, starred]
                last_line = cur
                gap = 0
                j += 1
                continue

            # A page number can land between two choices (page 502 puts "13"
            # between options b and c).  Stepping over it keeps the question
            # whole instead of splitting it into two short runs.
            if cur.kind == "skip":
                j += 1
                continue

            # Allow wrapped continuation text inside a run.
            if cur.kind == "text" and opts and gap == 0 and len(cur.text) < 130:
                prev = last_line or lines[j - 1]
                same_col = abs(cur.x0 - prev.x0) < 40 or cur.x0 > prev.x0
                close = (cur.page == prev.page and cur.y0 - prev.y1 < 8)
                if same_col and close:
                    k = next(reversed(opts))
                    body = (opts[k][0] + " " + cur.text).strip()
                    starred = is_star_marked(body)
                    opts[k][0] = clean_star(body)
                    opts[k][1] = opts[k][1] or starred
                    last_line = cur
                    j += 1
                    continue
            break

        if len(opts) >= 2 and not is_prose_run(opts):
            runs.append((start, j - 1, opts))
            i = j
        else:
            i = start + 1
    return runs


# Real MCQ choices in this document top out around 80 characters.  Bulleted
# explanation paragraphs also parse as choice lines, so a run whose bodies read
# as prose is discarded rather than emitted as a phantom question.
PROSE_MEDIAN = 130
PROSE_MAX = 400


def is_prose_run(opts):
    lens = sorted(len(v[0]) for v in opts.values())
    median = lens[len(lens) // 2]
    return median > PROSE_MEDIAN or lens[-1] > PROSE_MAX


# --------------------------------------------------------------------------
# Answer resolution
# --------------------------------------------------------------------------
LETTER_AT_START = re.compile(r"^\(?([A-Ha-h])\)?(?![A-Za-z0-9])")
# Only "vs"/"or"/"and"-style joiners with an UPPERCASE letter count as a second
# candidate.  A bare comma plus a lowercase word matched the article in
# "C, a cilioretinal artery is present", inventing an ambiguity that the source
# never expressed.
AMBIG_JOIN = re.compile(r"^(?:vs\.?|or|/|&|and)\s*\(?([A-H])\)?(?![A-Za-z0-9])")
# A capital letter preceded by a number is a unit, not an option: the key
# "+16.54 D" is dioptres, and reading it as choice D was a wrong answer.
LETTER_ANYWHERE = re.compile(
    r"(?:^|[\s(])\(?([A-H])\)?(?=[\s).,:;]|$)(?<![0-9.]\s[A-H])")
# Prose that rules an option OUT, or supersedes an earlier key, must never be
# mined for a letter -- the letter present is the one that is NOT the answer.
EXCLUSION_RE = re.compile(
    r"\b(except|not\b|isn'?t|aren'?t|wrong|incorrect|rules?d?\s+out|"
    r"other\s+than|apart\s+from|rather\s+than)\b", re.I)
SUPERSEDED_RE = re.compile(
    r"\b(previously|prev\.|was\s+answered|probably|might\s+be|could\s+be|"
    r"should\s+be|not\s+sure|unsure|incomplete)\b", re.I)


def trim_note(text):
    """Tidy the remark trailing an answer key without unbalancing its brackets."""
    t = text.strip(" .:;-")
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1].strip()
    elif t.startswith("(") and ")" not in t:
        t = t[1:].strip()
    elif t.endswith(")") and "(" not in t:
        t = t[:-1].strip()
    return t.strip(" .:;-")


def resolve_answer(answer_text, agree_text, options, starred):
    """
    Map a raw answer string onto an option key.

    Returns (key, note).  key is None when unresolvable.  Ambiguous source keys
    ("C vs D") resolve to the first-listed letter but the ambiguity is recorded
    in the note so the reader is never misled about the source's confidence.
    """
    note = ""
    at = (answer_text or "").strip()

    if at:
        m = LETTER_AT_START.match(at)
        if m:
            key = m.group(1).upper()
            rest = trim_note(at[m.end():])
            amb = AMBIG_JOIN.match(rest)
            if amb:
                alt = amb.group(1).upper()
                note = f"The source is undecided between {key} and {alt}."
                rest = trim_note(rest[amb.end():])
            if rest:
                note = (note + " " + rest).strip()
            if key in options:
                return key, note
            return None, note

        # Textual answer: match against option bodies.
        low = at.lower().strip(" .")
        for k, v in options.items():
            vb = v.lower().strip(" .")
            if vb and (low == vb or (len(vb) > 6 and vb in low) or
                       (len(low) > 6 and low in vb)):
                return k, ""

        # Prose answer that still names a letter, e.g.
        # "both are correct but more with A."  This is the riskiest path in the
        # parser -- prose keys are ~60x likelier to be misread than a plain
        # "Answer: X" -- so anything hedged, negated or superseded is refused
        # outright and lands in the reject log instead of guessing.
        if not (EXCLUSION_RE.search(at) or SUPERSEDED_RE.search(at)):
            hits = [h for h in LETTER_ANYWHERE.findall(at) if h in options]
            if len(set(hits)) == 1:
                return hits[0], at

    if len(starred) == 1:
        remark = (agree_text or "").strip()
        if at:
            # A star and a written verdict can disagree; surface the prose
            # rather than letting the star silently win.
            remark = (remark + " The source also notes: " + at).strip()
        return starred[0], remark
    if len(starred) > 1:
        return starred[0], "The source marks more than one choice as correct."
    return None, (note or at)


# --------------------------------------------------------------------------
# Question assembly
# --------------------------------------------------------------------------
STEM_STOP = {"answer", "agree", "expl", "ref", "opt", "bullet", "numopt",
             "year", "subspec", "incomplete"}
MAX_STEM_LINES = 9
MAX_STEM_CHARS = 420
# Whitespace separates questions here far more reliably than any keyword, but
# line pitch varies by section (12pt Calibri in 2025, widely-leaded Arial in
# 2015), so the threshold is relative to each page's own median pitch rather
# than a fixed number of points.
BLOCK_GAP_RATIO = 1.6
# A bare URL or a "Resource:"/"Reference:" line closes out the previous item, so
# the stem walk must not step over one.
# A URL that wrapped across lines leaves a tail carrying no scheme, which the
# stem walk would otherwise swallow ("...%20secondary%20to%20chronic%20papilledema.
# A preterm infant, GA= 27 weeks ..."). Percent-escapes and text-fragment
# anchors identify those continuation lines.
STEM_BOUNDARY_RE = re.compile(
    r"(https?://|www\.|\bResources?\s*:|\bReferences?\s*:"
    r"|%[0-9A-Fa-f]{2}|#:~:text=)", re.I)

# Parts of the 2016 section run the first choice on the same line as the stem
# ("What is the most likely etiology: a. DM"), so the detected run starts at B
# and choice A would otherwise be lost -- and left corrupting the stem text.
INLINE_OPT_RE = re.compile(r"\s([a-hA-H])\s*[.)]\s+(\S.*)$")


def peel_inline_options(stem, opts):
    keys = list(opts.keys())
    while keys and keys[0] != "A":
        want = chr(ord(keys[0]) - 1)
        m = INLINE_OPT_RE.search(stem)
        if not m or m.group(1).upper() != want:
            break
        body = m.group(2).strip()
        if len(body) > 90:
            break
        merged = collections.OrderedDict([(want, body)])
        merged.update(opts)
        opts = merged
        stem = stem[:m.start()].strip()
        keys = list(opts.keys())
    return stem, opts


class Q:
    def __init__(self):
        self.page = 0
        self.y0 = 0.0
        self.year = None
        self.subspec = None
        self.number = None
        self.stem = ""
        self.options = collections.OrderedDict()
        self.starred = []
        self.answer_raw = ""
        self.agree = ""
        self.explanation = ""
        self.reference = ""
        self.images = []
        self.incomplete = False
        self.bulleted = False
        self.end_page = 0


def page_pitch(lines):
    """Median baseline-to-baseline distance per page, used to size the gap that
    separates one question block from the next."""
    per_page = collections.defaultdict(list)
    for a, b in zip(lines, lines[1:]):
        if a.page == b.page:
            d = b.y0 - a.y0
            if 1.0 < d < 60.0:
                per_page[a.page].append(d)
    out = {}
    for page, gaps in per_page.items():
        gaps.sort()
        out[page] = gaps[len(gaps) // 2]
    return out


def find_stem_start(lines, run_start, floor, pitch):
    """
    Walk back from an option run to the first line of its stem.

    Returns (index, question_number).  The walk stops at any line that belongs
    to the previous question -- its answer, explanation, reference or choices --
    so a stem never absorbs the prose above it.
    """
    i = run_start - 1
    steps = 0
    number = None
    first = run_start
    chars = 0
    while i > floor and steps < MAX_STEM_LINES:
        ln = lines[i]
        if ln.kind == "skip":
            i -= 1
            continue
        if ln.kind not in ("text", "numopt"):
            break
        if STEM_BOUNDARY_RE.search(ln.text):
            break                      # a URL or "Resource:" ends the previous item
        nxt = lines[i + 1]
        if (first < run_start and ln.page == nxt.page
                and nxt.y0 - ln.y0 > BLOCK_GAP_RATIO * pitch.get(ln.page, 16.0)):
            # A visual break ends the stem -- but never before it has taken a
            # single line, or a question whose stem sits above a wide gap would
            # be emptied and dropped instead of merely trimmed.
            break
        m = QNUM_RE.match(ln.text)
        if m and (ln.bold or len(m.group(2)) > 10 or not m.group(2).strip()):
            number = int(m.group(1))
            first = i
            break
        chars += len(ln.text)
        if chars > MAX_STEM_CHARS:
            break
        first = i
        i -= 1
        steps += 1
    return first, number


def assemble(lines, runs, year_at, subspec_at):
    """
    Build questions from option runs.

    Stems are resolved for every run FIRST, because a question's explanation
    must stop where the next question's stem begins -- not where the next
    option run begins.  Bounding on the run start let every explanation swallow
    the stem that followed it.
    """
    pitch = page_pitch(lines)
    stems = []
    floor = -1
    for run_start, run_end, _ in runs:
        first, number = find_stem_start(lines, run_start, floor, pitch)
        stems.append((first, number))
        floor = run_end

    questions = []
    for ri, (run_start, run_end, opts) in enumerate(runs):
        q = Q()
        q.options = collections.OrderedDict((k, v[0]) for k, v in opts.items())
        q.starred = [k for k, v in opts.items() if v[1]]
        q.bulleted = lines[run_start].kind == "bullet"

        first, number = stems[ri]
        q.number = number
        parts = []
        for ln in lines[first:run_start]:
            if ln.kind == "skip":
                continue
            text = ln.text
            if ln is lines[first] and number is not None:
                m = QNUM_RE.match(text)
                if m:
                    text = m.group(2).strip()
            if text:
                parts.append(text)
        q.stem = re.sub(r"\s+", " ", " ".join(parts)).strip()
        q.stem, q.options = peel_inline_options(q.stem, q.options)

        anchor = lines[first]
        q.page, q.y0 = anchor.page, anchor.y0
        # The last page this question's own text reaches.  A figure that lives
        # beyond it belongs to a later recall, not to this one.
        q.end_page = max(anchor.page, lines[run_end].page)
        q.year = year_at(run_start)
        q.subspec = subspec_at(run_start)

        # Explanation runs to the start of the NEXT question's stem.
        stop = stems[ri + 1][0] if ri + 1 < len(runs) else len(lines)
        expl, ans, ref = [], [], ""
        j = run_end + 1
        seen_terminator = False
        in_ref = False
        while j < stop:
            ln = lines[j]
            if ln.kind == "answer":
                ans.append(ln.body)
                seen_terminator = True
            elif ln.kind == "agree":
                q.agree = ln.body
                if ln.body:
                    expl.append(ln.body)
                seen_terminator = True
            elif ln.kind == "expl":
                if ln.body:
                    expl.append(ln.body)
                in_ref = False
                seen_terminator = True
            elif ln.kind == "ref":
                ref = ln.body
                in_ref = True
                seen_terminator = True
            elif ln.kind == "incomplete":
                q.incomplete = True
                seen_terminator = True
            elif ln.kind in ("year", "subspec", "skip"):
                pass
            elif ln.kind in ("opt", "numopt"):
                break
            elif ln.kind == "bullet":
                # "\u2022" marks explanation bullets far more often than choices;
                # the stop bound already keeps a real choice run out of here.
                if seen_terminator and ln.body:
                    expl.append(ln.body)
            elif (not seen_terminator and j <= run_end + 2
                  and BARE_LETTER_RE.match(ln.text)):
                # Some entries give the key as a bare letter on its own line,
                # with no "Answer:" label.
                ans.append(BARE_LETTER_RE.match(ln.text).group(1))
                seen_terminator = True
            elif BARE_QNUM_RE.match(ln.text):
                pass          # the next recall's list number, not explanation
            elif (NUMBERED_RECALL_RE.match(ln.text)
                  and ln.x0 <= anchor.x0 + RECALL_MARGIN_SLACK):
                break         # a new recall starts here, even if it forms no run
            elif seen_terminator:
                if in_ref and len(ref) < 90:
                    ref = (ref + " " + ln.text).strip()
                else:
                    in_ref = False
                    expl.append(ln.text)
            j += 1

        q.answer_raw = " ".join(a for a in ans if a).strip()
        q.explanation = re.sub(r"\s+", " ", " ".join(expl)).strip()
        q.reference = ref.strip()
        questions.append(q)
    return questions


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------
def collect_images(doc):
    """Extract content images; drop page furniture and decorations."""
    pages_per_xref = collections.Counter()
    for i in range(doc.page_count):
        for img in doc[i].get_images(full=True):
            pages_per_xref[img[0]] += 1

    os.makedirs(IMG_DIR, exist_ok=True)
    saved, by_page, skipped = {}, collections.defaultdict(list), collections.Counter()
    float_like = set()

    for i in range(doc.page_count):
        page = doc[i]
        pw, ph = page.rect.width, page.rect.height
        for img in page.get_images(full=True):
            xref = img[0]
            if pages_per_xref[xref] > 3:
                skipped["repeated_furniture"] += 1
                continue
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                skipped["no_rect"] += 1
                continue
            if not rects:
                skipped["no_rect"] += 1
                continue
            if len(rects) > 2:
                skipped["tiled_background"] += 1
                continue
            rect = rects[0]
            if rect.width >= pw * 0.97 and rect.height >= ph * 0.6:
                skipped["full_bleed"] += 1
                continue
            if rect.width < 24 or rect.height < 24:
                skipped["tiny_placement"] += 1
                continue
            try:
                info = doc.extract_image(xref)
            except Exception:
                skipped["extract_failed"] += 1
                continue
            if info["width"] < 60 or info["height"] < 60:
                skipped["low_res"] += 1
                continue

            if rect.x0 > 0.42 * pw:
                # Word anchors a right-column float beside the paragraph it was
                # inserted at, which may belong to the recall above or below.
                # Measured at 31% misplaced against 7.4% for inline figures.
                float_like.add(xref)
            if xref not in saved:
                digest = hashlib.md5(info["image"]).hexdigest()[:10]
                ext = {"jpeg": "jpg", "jpg": "jpg", "png": "png"}.get(info["ext"], "png")
                name = f"p{i+1:03d}_{digest}.{ext}"
                with open(os.path.join(IMG_DIR, name), "wb") as fh:
                    fh.write(info["image"])
                saved[xref] = f"/images/promotion/{name}"
            by_page[i + 1].append((rect.y0, rect.y1, xref, saved[xref]))

    for k in by_page:
        by_page[k].sort()
    floats = {saved[x] for x in float_like if x in saved}
    return by_page, skipped, saved, floats


class SpanBarrier:
    """
    A year or subspecialty heading.  It owns no figure, but no figure may cross
    it either: when several consecutive recalls fail to parse, the last
    surviving question's span would otherwise run past a "2021:" header and
    collect the next year's photographs.
    """

    def __init__(self, page, y0):
        self.page, self.y0 = page, y0
        self.images = []
        self.barrier = True


class ImageOnlyAnchor:
    """
    A recall that exists only as a screenshot.  It leaves nothing in the text
    layer but its list number, so it never forms an option run -- yet it still
    owns its image and must claim it, or that image drifts onto the previous
    question.
    """

    def __init__(self, page, y0, number):
        self.page, self.y0, self.number = page, y0, number
        self.images = []
        self.image_only = True
        self.barrier = False


    # Body text and list numbers live in the left half of the page; the running
    # page-number footer sits out at x ~= 507-521.
FOOTER_X = 300.0
# A figure sits on its question's page or, when the question straddles a page
# break, the next one.  Anything further away is drift.
MAX_IMAGE_PAGE_SPAN = 1
# How far below a figure's bottom edge its owning stem may sit.
BASELINE_SLACK = 8.0
# How far right of the left text column a question number may still sit.
LEFT_MARGIN_SLACK = 22.0


def find_image_only_anchors(page_lines, questions):
    """
    Bare question-number lines that no option run covers.

    Every page from 298 on carries a footer number, which also matches
    BARE_QNUM_RE.  Admitting those created a phantom anchor at the bottom of
    each page that then claimed everything down the following page, stealing
    figures from real questions -- so footers are excluded by position, and
    `skip` lines (already classified as page furniture) are excluded outright.
    """
    claimed = {(q.page, round(q.y0, 1)) for q in questions}
    anchors = []
    for lines in page_lines:
        if not lines:
            continue
        # Question numbers start at the page's leftmost text column; a numbered
        # item inside an explanation is indented past it.  Without this gate the
        # anchor set balloons from ~40 to ~800 and swallows figures that belong
        # to real questions.
        margin = min(ln.x0 for ln in lines if ln.x0 < FOOTER_X) \
            if any(ln.x0 < FOOTER_X for ln in lines) else 0.0
        for ln in lines:
            if ln.kind not in ("text", "numopt") or ln.x0 >= FOOTER_X:
                continue
            if (ln.page, round(ln.y0, 1)) in claimed:
                continue
            m = BARE_QNUM_RE.match(ln.text)
            if not m and ln.x0 <= margin + LEFT_MARGIN_SLACK:
                # A numbered line WITH text at the left margin is a recall whose
                # choices never parsed: it forms no option run, so without an
                # anchor its figure drifts onto a neighbouring question.
                m = QNUM_RE.match(ln.text)
            if m:
                anchors.append(ImageOnlyAnchor(ln.page, ln.y0, int(m.group(1))))
    return anchors


def find_answer_anchors(lines, runs, claimed):
    """
    Recall boundaries derived from answer lines.

    Many recalls -- especially through the subspecialty-major 2018-2022 block --
    preserve only a single choice, so they form no option run and the parser
    never sees them.  They still end in "Answer:", though, and the stem above
    that line still owns whatever figure sits beside it.  Without an anchor
    there, those figures drift onto the previous question that did parse.

    These anchors publish nothing; they exist purely to stop a span.
    """
    covered = set()
    for (run_start, run_end, _) in runs:
        covered.update(range(run_start, run_end + 1))

    pitch = page_pitch(lines)
    anchors = []
    for i, ln in enumerate(lines):
        if ln.kind not in ("answer", "agree") or i in covered:
            continue
        # Walk back to the stem this answer belongs to.
        j = i - 1
        first = i
        steps = 0
        while j >= 0 and steps < MAX_STEM_LINES:
            prev = lines[j]
            if prev.kind in ("answer", "agree", "expl", "ref", "year",
                             "subspec", "incomplete"):
                break
            if prev.kind == "skip":
                j -= 1
                continue
            nxt = lines[j + 1]
            if (first < i and prev.page == nxt.page
                    and nxt.y0 - prev.y0 > BLOCK_GAP_RATIO * pitch.get(prev.page, 16.0)):
                break
            first = j
            j -= 1
            steps += 1
        if first == i:
            continue
        anchor = lines[first]
        if (anchor.page, round(anchor.y0, 1)) in claimed:
            continue
        anchors.append(ImageOnlyAnchor(anchor.page, anchor.y0, 0))
        claimed.add((anchor.page, round(anchor.y0, 1)))
    return anchors


def find_span_barriers(page_lines):
    """Year and subspecialty headings, as span terminators only."""
    return [SpanBarrier(ln.page, ln.y0)
            for lines in page_lines for ln in lines
            if ln.kind in ("year", "subspec")]


def bind_images(questions, extra_anchors, barriers, by_page):
    """
    Assign each image to the question whose vertical span contains it.

    A question's span runs from its stem anchor to the next anchor, crossing
    page boundaries.  Position-based binding is what prevents the off-by-one
    drift that index-based linking produced previously.

    One special case takes priority: Word renders an inline image's list number
    at the image's *baseline*, so a bare "2." can sit level with the bottom of
    the picture it labels.  When an anchor falls inside an image's vertical
    span, that anchor owns the image regardless of what precedes it.
    """
    anchors = sorted(list(questions) + list(extra_anchors) + list(barriers),
                     key=lambda a: (a.page, a.y0))
    if not anchors:
        return set(), []
    max_page = max(by_page) if by_page else 0
    used = set()

    # Pass 1 -- Word renders an inline image's list number at the image's
    # BASELINE, so the stem that owns a figure often sits level with its bottom
    # edge rather than above it.  Any anchor may claim on that basis, but where
    # several fall inside one figure's span the LAST one wins: that is the one
    # at the baseline, and preferring the first let a tall figure be stolen by
    # a stem far above its true owner.
    by_anchor_page = collections.defaultdict(list)
    for a in anchors:
        if not getattr(a, "barrier", False):
            by_anchor_page[a.page].append(a)
    for page, items in by_page.items():
        for (iy0, iy1, xref, path) in items:
            tag = (page, xref, round(iy0, 1))
            if tag in used:
                continue
            inside = [a for a in by_anchor_page.get(page, [])
                      if iy0 - 2 <= a.y0 <= iy1 + BASELINE_SLACK]
            if inside:
                owner = max(inside, key=lambda a: a.y0)
                owner.images.append(path)
                used.add(tag)

    # Pass 2 -- ordinary top-down containment.
    for idx, a in enumerate(anchors):
        if getattr(a, "barrier", False):
            continue
        nxt = anchors[idx + 1] if idx + 1 < len(anchors) else None
        end_pg = nxt.page if nxt else max_page + 1
        end_y = nxt.y0 if nxt else 10 ** 6
        # Never reach more than one page past the anchor.  When the next
        # anchor is several pages away -- because the questions in between were
        # not parsed -- an uncapped span hoovers up every figure it crosses and
        # staples them all onto one question.  Leaving them unbound makes them
        # invisible, which is far better than showing the wrong photo.
        last_page = min(end_pg, max_page, a.page + MAX_IMAGE_PAGE_SPAN)
        for p in range(a.page, last_page + 1):
            for (iy0, iy1, xref, path) in by_page.get(p, []):
                tag = (p, xref, round(iy0, 1))
                if tag in used:
                    continue
                after_start = (p > a.page) or (iy1 > a.y0 - 2)
                before_end = (p < end_pg) or (p == end_pg and iy0 < end_y - 2)
                if after_start and before_end:
                    a.images.append(path)
                    used.add(tag)

    orphans = []
    for p, items in by_page.items():
        for (iy0, iy1, xref, path) in items:
            if (p, xref, round(iy0, 1)) not in used:
                orphans.append({"page": p, "y": round(iy0, 1), "image": path})
    return used, orphans


# A stem that names its own picture: these questions are unanswerable without
# the figure, so a missing one is a hard failure rather than a cosmetic gap.
DEMANDS_FIGURE_RE = re.compile(
    r"\b(photo(graph)?\s+(shown|above|attached)|pictured\s+above|exact\s+pict"
    r"|picture\s+(shown|above|attached|of)|image\s+(shown|above|showing)"
    r"|shown\s+(in\s+the\s+)?(photo|picture|image|figure)|see\s+(the\s+)?pic"
    r"|as\s+shown|attached\s+(picture|photo|image)"
    r"|exactly\s+this\s+(picture|photo|image)|this\s+exact\s+(picture|photo|image)"
    r"|same\s+(exact\s+)?(picture|photo|pic))", re.I)


# Any mention of a picture at all, however loose.  Used only to establish that a
# question does NOT reference one, so it is deliberately broad.
MENTIONS_FIGURE_RE = re.compile(
    r"\b(photo|picture|pic\b|pics\b|image|figure|slide|shown|attached|"
    r"appearance|as\s+seen|depicted|illustrat)", re.I)


def page_of_figure(path):
    """Page encoded in an extracted figure's filename."""
    m = re.match(r"p(\d+)_", os.path.basename(path))
    return int(m.group(1)) if m else -1


def reallocate_from_silent_neighbours(questions):
    """
    Move a figure from a question that never mentions one to an adjacent
    question that explicitly asks for it.

    Right-column floats are the worst-placed figures in this document (measured
    at 31% wrong against 7.4% for inline ones) because Word anchors them beside
    the paragraph they were inserted at, which can be a recall above or below.
    Geometry alone cannot settle it -- but the text usually can: page 627's
    "greatest refractive power" recall ends "40-44 D See pic" and has no figure,
    while the neighbour holding the float asks about retrobulbar anaesthesia and
    mentions no image at all.

    Applied only when the requester names a picture, the donor names none, and
    exactly one candidate exists, so an ambiguous case is left alone.
    """
    published = sorted(questions, key=lambda q: (q.page, q.y0))
    moved = 0
    for idx, q in enumerate(published):
        if q.images:
            continue
        cue_in_stem = bool(DEMANDS_FIGURE_RE.search(q.stem))
        if not (cue_in_stem or DEMANDS_FIGURE_RE.search(q.explanation or "")):
            continue
        candidates = []
        for off in (-2, -1, 1, 2):
            j = idx + off
            if not (0 <= j < len(published)):
                continue
            other = published[j]
            if not other.images or abs(other.page - q.page) > 1:
                continue
            if MENTIONS_FIGURE_RE.search(other.stem):
                continue                  # the donor may well own it
            if DEMANDS_FIGURE_RE.search(other.explanation or ""):
                continue                  # donor's own explanation claims a figure
            for path in other.images:
                # A cue found only in the explanation is weaker evidence: an
                # explanation can still absorb wording from an unparsed recall
                # next to it.  Trust it for a figure on the question's own page,
                # but require the stem itself to ask before moving one across a
                # page boundary.
                if not cue_in_stem and page_of_figure(path) != q.page:
                    continue
                candidates.append((other, path))
        if len(candidates) != 1:
            continue
        donor, path = candidates[0]
        donor.images.remove(path)
        q.images.append(path)
        moved += 1
    return moved


def reclaim_demanded_figures(questions, extra_anchors, by_page):
    """
    Give a figure back to a question that explicitly asks for one.

    Boundary anchors stop drift, but any figure they claim is displayed nowhere.
    When a published question names its own picture, has none, and exactly one
    figure sits unshown within its span on its own page, that figure is far more
    likely to be the one it means than to belong to the silent recall that
    happens to bracket it.
    """
    published = sorted(questions, key=lambda q: (q.page, q.y0))
    silent = [a for a in extra_anchors if a.images]
    held = {}
    for a in silent:
        for path in a.images:
            held.setdefault(path, a)

    reclaimed = 0
    for idx, q in enumerate(published):
        if q.images or not DEMANDS_FIGURE_RE.search(q.stem):
            continue
        nxt = published[idx + 1] if idx + 1 < len(published) else None
        end_y = nxt.y0 if (nxt and nxt.page == q.page) else 10 ** 6

        candidates = []
        for (iy0, iy1, xref, path) in by_page.get(q.page, []):
            owner = held.get(path)
            if owner is None or path not in owner.images:
                continue
            # Same span the question itself occupies, give or take a baseline.
            if iy1 > q.y0 - BASELINE_SLACK and iy0 < end_y + BASELINE_SLACK:
                candidates.append((iy0, path, owner))
        if len(candidates) != 1:
            continue                      # ambiguous -- leave it unshown
        _, path, owner = candidates[0]
        owner.images.remove(path)
        q.images.append(path)
        reclaimed += 1
    return reclaimed


# --------------------------------------------------------------------------
# Emission
# --------------------------------------------------------------------------
MIN_STEM = 10
JUNK_OPT_RE = re.compile(r"^[\s.…?\-_*]*$")
MAX_OPTIONS = 6
QUESTION_CUE_RE = re.compile(
    r"(\?|what|which|how|where|when|why|most likely|next step|diagnosis|"
    r"management|treatment|true|false|associated)", re.I)


def looks_like_question(stem, opts):
    """
    Distinguish a genuine recall the source never keyed from a bulleted list
    inside an explanation that merely parses like a choice run.
    """
    if len(stem) < 25 or not opts:
        return False
    if not QUESTION_CUE_RE.search(stem):
        return False
    if stem.lstrip().startswith("-"):
        return False
    return sum(len(v) for v in opts.values()) / len(opts) <= 90


def relabel_if_mislettered(opts, answer_raw):
    """
    A few recalls letter their choices from the middle of the alphabet
    ("D. Eye shield / E. ... / F. ... / G. ...") while the key still says "A".

    Remapping to A.. is only safe when several letters were skipped: a run
    starting at B with the key pointing at A is far more likely to be a genuinely
    lost first choice, and remapping that would silently move the answer.
    """
    keys = list(opts.keys())
    if not keys or keys[0] < "C":
        return opts
    if [ord(k) for k in keys] != list(range(ord(keys[0]), ord(keys[0]) + len(keys))):
        return opts
    m = LETTER_AT_START.match((answer_raw or "").strip())
    if not m:
        return opts
    want = m.group(1).upper()
    if want in opts or ord(want) - ord("A") >= len(keys):
        return opts
    return collections.OrderedDict(
        (chr(ord("A") + i), opts[k]) for i, k in enumerate(keys))


# Confidence in a figure's placement, from what measurement actually showed
# predicts error: a stem that names its own picture was right in every sampled
# case; a right-column float attached to a stem that never mentions an image was
# the shape of every confirmed misplacement.
def figure_confidence(stem, explanation, images, float_paths):
    if not images:
        return None
    names_it = bool(DEMANDS_FIGURE_RE.search(stem))
    mentions = bool(MENTIONS_FIGURE_RE.search(stem)) or \
        bool(DEMANDS_FIGURE_RE.search(explanation or ""))
    is_float = any(u in float_paths for u in images)
    if names_it:
        return "high"
    if not mentions and is_float:
        return "low"
    if not mentions or is_float:
        return "medium"
    return "high"


def build(questions, float_paths=frozenset()):
    out, rejects = [], []
    for q in questions:
        opts = collections.OrderedDict()
        for k, v in q.options.items():
            v = re.sub(r"\s+", " ", v).strip()
            if v and not JUNK_OPT_RE.match(v):
                opts[k] = v
        opts = relabel_if_mislettered(opts, q.answer_raw)

        reason = None
        if len(opts) < 2:
            reason = "fewer than 2 usable options"
        elif q.bulleted and not q.stem.rstrip().endswith(("?", ":", ":-")):
            # Bulleted choices in this document always follow a stem that ends
            # in "?" or ":".  Anything else is prose with a list under it.
            reason = "bulleted list inside an explanation, not a question"
        elif len(opts) > MAX_OPTIONS:
            # Every genuine recall here offers 2-5 choices.  A longer run is a
            # reference list that happens to be formatted like one.
            reason = f"{len(opts)} options: a reference list, not a question"
        key, note = resolve_answer(q.answer_raw, q.agree, opts, q.starred)
        if reason is None and key is None:
            reason = f"unresolvable answer ({q.answer_raw[:60]!r})"
        if reason is None and len(q.stem) < MIN_STEM and not q.images:
            reason = "stem too short and no image"

        if reason:
            genuine = looks_like_question(q.stem, opts)
            rejects.append({
                "page": q.page, "year": q.year, "number": q.number,
                "stem": q.stem[:220], "options": dict(opts),
                "answer_raw": q.answer_raw, "images": q.images,
                "reason": reason,
                "looks_like_question": genuine,
            })
            # An unkeyed, non-question run is a bulleted list living inside an
            # explanation (mnemonics, sign lists).  Give that text back to the
            # question it was explaining instead of discarding it.
            list_shaped = ("list inside an explanation" in reason
                           or "reference list" in reason)
            if (list_shaped or (not genuine and not q.answer_raw.strip()))                     and out and opts:
                tail = "; ".join(opts.values())
                prev = out[-1]
                if prev["pdfPage"] >= q.page - 1 and len(prev["explanation"]) < 4000:
                    extra = f"{q.stem} {tail}".strip()
                    prev["explanation"] = f"{prev['explanation']} {extra}".strip()
            continue

        parts = []
        if q.incomplete:
            parts.append("The source flags this recall as incomplete.")
        if note:
            parts.append(note)
        if q.explanation:
            parts.append(q.explanation)
        if q.reference:
            parts.append(f"Reference: {q.reference}")
        explanation = re.sub(r"\s+", " ", " ".join(parts)).strip()
        if not explanation:
            explanation = "No explanation was provided in the source document."

        item = {
            "id": 0,
            "source": f"promotion-{q.year}",
            "question": q.stem if len(q.stem) >= MIN_STEM else "See the image below.",
            "options": dict(opts),
            "correctAnswer": key,
            "explanation": explanation,
            "year": q.year,
            "subspecialty": q.subspec or "Miscellaneous",
            "pdfPage": q.page,
        }
        if q.images:
            conf = figure_confidence(q.stem, explanation, q.images, float_paths)
            if conf and conf != "high":
                item["figureConfidence"] = conf
            # Convention across every existing bank: imageUrl is the primary
            # figure and imageUrls holds only the *additional* ones.  QuizCard
            # renders the two separately, so repeating the primary inside the
            # array shows the same picture twice.
            seen = {q.images[0]}
            extra = [u for u in q.images[1:]
                     if u not in seen and not seen.add(u)]
            item["imageUrl"] = q.images[0]
            if extra:
                item["imageUrls"] = extra
        out.append(item)
    return dedupe(out), rejects


def dedupe(questions):
    """
    Drop verbatim repeats within a bank.  The source genuinely duplicates some
    recalls (2024 lists the pterygium question twice, back to back); keeping
    both just makes the reader answer the same card twice.
    """
    seen = {}
    kept = []
    for q in questions:
        sig = (q["question"].strip().lower(),
               tuple(sorted(v.strip().lower() for v in q["options"].values())),
               q["correctAnswer"], q["year"])
        if sig in seen:
            continue
        seen[sig] = True
        kept.append(q)
    return kept


# Some sittings survive almost entirely as screenshots and leave only a handful
# of text-layer recalls -- a two-question bank is just noise in the picker.  Any
# year below this threshold is folded into its nearest neighbour, and the bank
# is named after the years it actually ends up containing, so a merge that turns
# out to be unnecessary does not leave a misleading label behind.
MIN_BANK = 15


def bank_layout(years):
    """Map each year -> bank id, merging undersized years into a neighbour."""
    ordered = sorted(years, reverse=True)
    banks = {}
    carry = []
    for year in ordered:
        carry.append(year)
        if sum(years[y] for y in carry) >= MIN_BANK:
            name = carry[-1] if len(carry) == 1 else f"{carry[-1]}-{carry[0]}"
            for y in carry:
                banks[y] = name
            carry = []
    if carry:                       # trailing remainder joins the last bank
        prev = banks.get(ordered[len(ordered) - len(carry) - 1]) if banks else None
        if prev:
            merged = sorted([y for y, b in banks.items() if b == prev] + carry)
            name = f"{merged[0]}-{merged[-1]}"
            for y, b in list(banks.items()):
                if b == prev:
                    banks[y] = name
            for y in carry:
                banks[y] = name
        else:
            name = f"{carry[-1]}-{carry[0]}" if len(carry) > 1 else carry[0]
            for y in carry:
                banks[y] = name
    return banks

CATEGORY = {"id": "promotion", "name": "Promotion Exam", "icon": "🎓"}


def write_manifest(by_bank):
    """Merge the Promotion banks into the app manifest, leaving others intact."""
    path = os.path.join(DATA_DIR, "manifest.json")
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    cats = [c for c in manifest.get("categories", []) if c["id"] != CATEGORY["id"]]
    cats.append(CATEGORY)
    manifest["categories"] = cats

    sets = [s for s in manifest["questionSets"] if s.get("category") != CATEGORY["id"]]

    # questionCount is derived, not hand-maintained: the pre-existing manifest
    # had lens-cataract-oq at 29 against a file holding 172, which showed a
    # wrong size in the picker.  Recomputing keeps every bank honest.
    for s in sets:
        path_ = os.path.join(DATA_DIR, s["file"])
        if os.path.exists(path_):
            with open(path_, encoding="utf-8") as fh2:
                actual = len(json.load(fh2))
            if actual != s.get("questionCount"):
                old = s.get("questionCount")
                print(f"  corrected {s['id']}: questionCount {old} -> {actual}")
                # Descriptions lead with the same number, so keep them in step.
                if old is not None:
                    s["description"] = re.sub(rf"\b{old}\b", str(actual),
                                              s.get("description", ""), count=1)
                s["questionCount"] = actual

    for bank in sorted(by_bank, reverse=True):
        qs = by_bank[bank]
        subs = collections.Counter(q["subspecialty"] for q in qs)
        top = ", ".join(n for n, _ in subs.most_common(3))
        sets.append({
            "id": f"promotion-{bank}",
            "name": f"Promotion {bank}",
            "description": f"{len(qs)} recalled questions from the {bank} "
                           f"promotion exam - {top}",
            "file": f"promotion-{bank}.json",
            "questionCount": len(qs),
            "category": CATEGORY["id"],
            "source": "Promotion",
        })
    manifest["questionSets"] = sets

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"\n  manifest updated: {len(by_bank)} Promotion banks registered")


def prune_unused_images(questions, shots, anchors, rejects=()):
    """
    Extraction writes every content image on a page, including the decorations
    on section title pages and the figures of candidates that were rejected.
    Nothing serves those, so drop them rather than ship them.

    Images belonging to screenshot-only recalls are kept: no question
    references them yet, but they are the raw material if those 127 recalls are
    ever OCR'd into real questions.
    """
    keep = set()
    for q in questions:
        if q.get("imageUrl"):
            keep.add(os.path.basename(q["imageUrl"]))
        for u in q.get("imageUrls", []):
            keep.add(os.path.basename(u))
    for s in shots:
        for u in s["images"]:
            keep.add(os.path.basename(u))
    for a in anchors:
        for u in a.images:
            keep.add(os.path.basename(u))
    # Recalls the source never keyed are held back from the published banks but
    # can still ship, reviewer-answered, in their own bank -- so their figures
    # have to survive the prune or those questions arrive with a broken image.
    for r in rejects:
        if r.get("looks_like_question"):
            for u in r.get("images") or ():
                keep.add(os.path.basename(u))

    freed = 0
    removed = 0
    for name in os.listdir(IMG_DIR):
        if name not in keep:
            path = os.path.join(IMG_DIR, name)
            freed += os.path.getsize(path)
            os.remove(path)
            removed += 1
    print(f"  pruned {removed} unreferenced images ({freed / 1e6:.1f} MB); "
          f"{len(keep)} kept")


def main():
    print("Parsing", os.path.basename(PDF))
    doc = fitz.open(PDF)
    page_lines = [classify(extract_lines(doc, i)) for i in range(doc.page_count)]

    by_page, skipped, saved, float_paths = collect_images(doc)
    print(f"  content images kept: {sum(len(v) for v in by_page.values())} "
          f"(unique files: {len(saved)})")
    print(f"  images skipped: {dict(skipped)}")

    all_questions = []
    section_anchors = []
    for start, end, default_year in SECTIONS:
        lines = []
        for pno in range(start - 1, min(end, doc.page_count)):
            lines.extend(page_lines[pno])

        # Precompute year/subspecialty in effect at each line index.
        years, subs = [], []
        cy, cs = default_year, None
        for ln in lines:
            if ln.kind == "year":
                cy = ln.key
            elif ln.kind == "subspec":
                cs = ln.key
            years.append(cy)
            subs.append(cs)

        runs = find_runs(lines)
        qs = assemble(lines, runs, lambda i: years[i], lambda i: subs[i])
        for q in qs:
            if q.year is None:
                q.year = default_year or "unknown"
        all_questions.extend(qs)
        section_anchors.extend(
            find_answer_anchors(lines, runs,
                                {(q.page, round(q.y0, 1)) for q in qs}))
        print(f"  pages {start:>3}-{end:<3} -> {len(runs):4d} option runs")

    screenshot_only = find_image_only_anchors(page_lines, all_questions)
    barriers = find_span_barriers(page_lines)
    print(f"  recall boundaries from answer lines: {len(section_anchors)}")
    _, orphans = bind_images(all_questions, screenshot_only + section_anchors,
                             barriers, by_page)
    reclaimed = reclaim_demanded_figures(all_questions,
                                         screenshot_only + section_anchors,
                                         by_page)
    moved = reallocate_from_silent_neighbours(all_questions)
    questions, rejects = build(all_questions, float_paths)

    shots = [{"page": a.page, "number": a.number, "images": a.images}
             for a in screenshot_only if a.images and a.number]
    print(f"\n  questions emitted: {len(questions)}")
    print(f"  rejected:          {len(rejects)}")
    print(f"  orphan images:     {len(orphans)}")
    print(f"  screenshot-only recalls (no text layer, excluded): {len(shots)}")
    print(f"  figures returned to questions that name a picture: {reclaimed}")
    print(f"  figures moved off a question that names none:        {moved}")

    per_year = collections.Counter(q["year"] for q in questions)
    banks = bank_layout(per_year)
    by_year = collections.defaultdict(list)
    for q in questions:
        by_year[banks[q["year"]]].append(q)

    print("\n  per-bank counts:")
    for y in sorted(by_year, reverse=True):
        img = sum(1 for q in by_year[y] if q.get("imageUrl"))
        print(f"    {y}: {len(by_year[y]):4d} questions ({img} with images)")

    os.makedirs(DATA_DIR, exist_ok=True)
    for bank, qs in by_year.items():
        qs.sort(key=lambda q: (q["year"], q["pdfPage"]))
        for i, q in enumerate(qs, 1):
            q["id"] = i
            q["source"] = f"promotion-{bank}"
        with open(os.path.join(DATA_DIR, f"promotion-{bank}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(qs, fh, ensure_ascii=False, indent=1)

    write_manifest(by_year)
    prune_unused_images(questions, shots, screenshot_only + section_anchors,
                        rejects)

    if glob.glob(os.path.join(REPORT_DIR, "ocr", "result_*.json")):
        print("\n  NOTE: transcribed screenshot recalls exist but were just\n"
              "  overwritten by this run. Restore them with:\n"
              "      python scripts/merge_ocr_recalls.py")

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "promotion_rejects.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rejects, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(REPORT_DIR, "promotion_orphan_images.json"), "w",
              encoding="utf-8") as fh:
        json.dump(orphans, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(REPORT_DIR, "promotion_screenshot_only.json"), "w",
              encoding="utf-8") as fh:
        json.dump(shots, fh, ensure_ascii=False, indent=1)

    print("\n  reject reasons:")
    for r, n in collections.Counter(
            x["reason"].split("(")[0].strip() for x in rejects).most_common():
        print(f"    {n:4d}  {r}")

    real = [r for r in rejects if r["looks_like_question"]]
    print(f"\n  of those rejects, {len(real)} read as genuine recalls the source "
          f"never keyed;\n  the remaining {len(rejects) - len(real)} are bulleted "
          f"lists inside explanations.")
    if real:
        print("  genuine-but-unkeyed by year:",
              dict(collections.Counter(r["year"] for r in real)))


if __name__ == "__main__":
    main()
