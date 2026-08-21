#!/usr/bin/env python3
"""
Render a bank as a plain review sheet, so a year can be checked in one read
before it is trusted for study.

Every question shows where its key came from, because they did not all come
from the same place: some the compiler wrote out, some are only a tick in the
exam screenshot, and a few the compiler openly hedged.

Usage:  python scripts/vision_review_sheet.py 2020 [-o out.html]
"""

import argparse
import collections
import html
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "public", "data")

KEY_LABEL = {
    "both": "key written out and ticked in the screenshot",
    "text": "key written out by the compiler",
    "marked_in_image": "key is only a tick in the screenshot",
}

CSS = """
:root{--bg:#faf9f7;--card:#fff;--ink:#1a1a2e;--ink2:#4a4a68;--mut:#9ca3af;
--line:#e8e6e1;--accent:#7c3aed;--accent-lt:#ede9fe;--ok:#166534;--ok-bg:#f0fdf4;
--warn:#92400e;--warn-bg:#fffbeb;--err:#b91c1c}
:root:not([data-theme="light"]){}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
--bg:#0c0c14;--card:#1a1a28;--ink:#eeeef4;--ink2:#a0a0c0;--mut:#5a5a7a;
--line:#2a2a40;--accent:#a78bfa;--accent-lt:#1e1533;--ok:#86efac;--ok-bg:#0f2417;
--warn:#fcd34d;--warn-bg:#3a2f14;--err:#fca5a5}}
:root[data-theme="dark"]{--bg:#0c0c14;--card:#1a1a28;--ink:#eeeef4;--ink2:#a0a0c0;
--mut:#5a5a7a;--line:#2a2a40;--accent:#a78bfa;--accent-lt:#1e1533;--ok:#86efac;
--ok-bg:#0f2417;--warn:#fcd34d;--warn-bg:#3a2f14;--err:#fca5a5}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.6 'DM Sans',system-ui,-apple-system,sans-serif;
-webkit-font-smoothing:antialiased}
.wrap{max-width:820px;margin:0 auto;padding:40px 20px 80px}
h1{font-size:30px;line-height:1.15;letter-spacing:-.02em;margin:0 0 6px}
.sub{color:var(--mut);font-size:14px;margin:0 0 26px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
gap:10px;margin-bottom:34px}
.stat{background:var(--card);border:1px solid var(--line);padding:12px 14px}
.stat b{display:block;font-size:22px;letter-spacing:-.01em}
.stat span{font-size:11.5px;color:var(--mut)}
.q{background:var(--card);border:1px solid var(--line);padding:18px;margin-bottom:14px}
.qh{display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.n{font-size:11px;font-weight:700;color:var(--mut);letter-spacing:.06em}
.tag{font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
padding:2px 7px;border:1px solid currentColor}
.t-key{color:var(--mut)}
.t-warn{color:var(--warn);background:var(--warn-bg);border-color:var(--warn)}
.t-auth{color:var(--accent);background:var(--accent-lt);border-color:var(--accent)}
.stem{font-weight:600;line-height:1.45;margin:0 0 12px;text-wrap:pretty}
ol{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:5px}
li{display:flex;gap:9px;align-items:flex-start;padding:7px 9px;border:1px solid var(--line)}
li.right{background:var(--ok-bg);border-color:var(--ok)}
.let{font-weight:700;font-size:12px;width:19px;flex:0 0 19px;text-align:center;
padding-top:1px;color:var(--mut)}
li.right .let{color:var(--ok)}
.expl{font-size:13.5px;color:var(--ink2);margin:12px 0 0;padding-top:11px;
border-top:1px solid var(--line);text-wrap:pretty}
.note{font-size:12.5px;color:var(--mut);margin:8px 0 0;font-style:italic}
.hint{font-size:12.5px;margin:9px 0 0;padding:7px 10px;background:var(--warn-bg);color:var(--ink2)}
a{color:var(--accent)}
"""


def render(bank, year):
    keyed = collections.Counter(q.get("keyFrom") for q in bank)
    unsure = [q for q in bank if q.get("sourceHint") is not None]
    authored = [q for q in bank if q.get("authoredDistractors")]
    figs = [q for q in bank if q.get("pageScanUrl")]
    subs = collections.Counter(q.get("subspecialty") for q in bank)

    out = [f"<title>Promotion {year} — recovered recalls</title>",
           f"<style>{CSS}</style>", '<div class="wrap">',
           f"<h1>Promotion {year}</h1>",
           f'<p class="sub">{len(bank)} recalls read off the source pages. '
           "This section was pasted into the document as screenshots, so the "
           "text parser saw none of it.</p>",
           '<div class="stats">',
           f'<div class="stat"><b>{len(bank)}</b><span>questions recovered</span></div>',
           f'<div class="stat"><b>{keyed["both"]}</b><span>key written out and ticked</span></div>',
           f'<div class="stat"><b>{keyed["marked_in_image"]}</b><span>key only ticked in the screenshot</span></div>',
           f'<div class="stat"><b>{len(unsure)}</b><span>compiler was unsure</span></div>',
           f'<div class="stat"><b>{len(authored)}</b><span>distractors written for this bank</span></div>',
           f'<div class="stat"><b>{len(subs)}</b><span>subspecialties</span></div>',
           "</div>"]

    for q in bank:
        out.append('<div class="q"><div class="qh">')
        out.append(f'<span class="n">Q{q["id"]} &middot; p.{q.get("pdfPage")} '
                   f'&middot; {html.escape(q.get("subspecialty") or "")}</span>')
        out.append(f'<span class="tag t-key">{KEY_LABEL.get(q.get("keyFrom"), "")}</span>')
        if q.get("sourceHint") is not None:
            wrote = q["sourceHint"] or "nothing"
            out.append(f'<span class="tag t-warn">unconfirmed &mdash; source wrote {html.escape(wrote)}</span>')
        if q.get("authoredDistractors"):
            out.append('<span class="tag t-auth">wrong options authored</span>')
        out.append("</div>")
        out.append(f'<p class="stem">{html.escape(q["question"])}</p><ol>')
        for letter in sorted(q["options"]):
            cls = " class=\"right\"" if letter == q["correctAnswer"] else ""
            out.append(f'<li{cls}><span class="let">{letter}</span>'
                       f'<span>{html.escape(q["options"][letter])}</span></li>')
        out.append("</ol>")
        if q.get("explanation"):
            out.append(f'<p class="expl">{html.escape(q["explanation"])}</p>')
        if q.get("sourceHint") is not None:
            wrote = q["sourceHint"]
            msg = ("The compiler left the answer line empty."
                   if wrote == "" else
                   f"Where the answer should be, the compiler wrote &ldquo;{html.escape(wrote)}&rdquo;.")
            out.append(f'<p class="hint">{msg} Check this one against the page before trusting it.</p>')
        if q.get("sourceNote"):
            out.append(f'<p class="note">{html.escape(q["sourceNote"])}</p>')
        out.append("</div>")

    out.append("</div>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("year")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    path = os.path.join(DATA, f"promotion-{args.year}.json")
    bank = json.load(open(path, encoding="utf-8"))
    out = args.out or os.path.join(ROOT, f"promotion-{args.year}-review.html")
    with io.open(out, "w", encoding="utf-8") as fh:
        fh.write(render(bank, args.year))
    print(f"{out}  ({len(bank)} questions)")


if __name__ == "__main__":
    main()
