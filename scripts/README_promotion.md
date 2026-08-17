# Promotion Exam pipeline

Turns `Promotion Exam ( 2025-2014).pdf` into the QuizVault **Promotion Exam**
category: 11 per-year banks under `public/data/promotion-<year>.json`, with
figures under `public/images/promotion/`.

```bash
python scripts/parse_promotion.py       # 1. parse the text layer
python scripts/merge_ocr_recalls.py     # 2. fold in the transcribed screenshots
python scripts/merge_figure_links.py    # 3. reference links for doubtful figures
python scripts/merge_expert_review.py   # 4. reviewer second opinions + unkeyed bank
python scripts/render_page_scans.py     # 5. source-page scans (must run last)
```

**Run them in that order.** Step 1 is idempotent and owns the whole output: it
rewrites the bank files, re-extracts the images, merges its entries into
`public/data/manifest.json` (leaving other categories untouched), and deletes any
extracted image nothing references. Because it rewrites the banks, running it
alone drops everything steps 2-5 added — each later step puts its own part back,
and each is idempotent.

Step 5 runs last because which questions need a page scan depends on what step 4
produced. Steps 2-4 read their inputs from `scripts/ocr/`, `scripts/figures/` and
`scripts/review/` + `scripts/unkeyed/`, all of which are committed.

## Why the source is hard

661 pages compiled by hand over twelve sittings, then marked up on an iPad. It
carries at least six question layouts, and several traps that are worth knowing
about before changing anything:

| Trap | How it is handled |
|---|---|
| iPad handwriting is embedded as *text* | Apple Scribble uses dot-prefixed system fonts (`.SFUI-Regular_wdth_opsz1`) plus plain `Helvetica`/`HelveticaNeue` islands. Both families are dropped in `extract_lines`. |
| Question numbering is unreliable | It restarts, skips, disappears in the 2014/2017 sections, and gets swallowed by Word auto-lists (`3. 32- patient can see …`). Parsing anchors on **option runs**, never on numbers. |
| A page-number footer looks like a question number | Every page from 298 on has one. They are excluded by x-position (`FOOTER_X`); body text sits left of 300, footers around 507–521. |
| Word puts an inline image's list number at the image *baseline* | The stem owning a figure often sits level with its *bottom* edge, not above it. Any anchor inside `[top, bottom + 8pt]` may claim it, and where several qualify the **lowest** wins — that is the one at the baseline. Preferring the highest let a tall figure be taken by a stem far above its real owner. |
| Explanations contain bulleted lists | Those parse as choice runs. Rejected by `is_prose_run`, by the `MAX_OPTIONS` cap, and by requiring a bulleted question's stem to end in `?` or `:`. Their text is folded back into the explanation they belong to. |
| Ligature slots decode as punctuation | `ar=cle`, `la9ce`, `tu6s`, `hEps://`, `opWc`, `degenera-on`. Repair is token-aware so URL query strings and UUIDs survive (`fix_subset_font`). |
| Answers appear in ~six shapes | `Answer: B`, `Ans. B`, a bare letter on its own line, a trailing `*` on the correct choice, `Agree`, or prose. See `resolve_answer`. |

## The one rule worth preserving

**Never guess an answer key.** Prose answers are roughly 60× likelier to be
misread than a plain `Answer: X` — a capital letter in prose may be a unit
(`+16.54 D`), an *excluded* option (`all correct except C`) or a superseded one
(`previously answered as B`). Anything hedged or negated is refused and sent to
the reject log rather than published. A missing question costs a little study
material; a wrong key teaches the wrong medicine.

Figures follow the same principle: an image that cannot be placed confidently is
left unbound rather than attached to a neighbouring question.

## Output and reports

Alongside the banks the script writes three reports (gitignored) next to itself:

- `promotion_rejects.json` — every candidate not published, with the reason
- `promotion_screenshot_only.json` — recalls that exist only as a screenshot
- `promotion_orphan_images.json` — figures bound to nothing

## Auditing

```bash
python scripts/verify_promotion.py 2025 12 --render
python scripts/verify_promotion.py --sample 25 --seed 7 --with-images
python scripts/verify_promotion.py --page 405
```

Prints the emitted record beside the source page text (with and without the
handwriting layer) and renders the page to `scripts/_verify/` so an image
placement can be checked by eye.

## Screenshot recalls (step 2)

Recalls that exist only as a pasted image leave nothing for step 1 to parse.
`build_ocr_worklist.py` batches those images, they are transcribed
image-by-image, and `merge_ocr_recalls.py` folds the usable results back in,
tagging each with `"ocr": true` and keeping the source screenshot as its figure.

Acceptance is narrow on purpose. A transcription is refused unless it is a real
question with ≥2 legible choices **and an answer visibly marked in that same
image**. A letter appearing in a neighbouring screenshot is not evidence for this
one. Of 104 screenshots: **41 became questions**, 60 were figures or explanation
excerpts, 1 was a low-confidence read, 1 had no marked answer, 1 was a
same-year duplicate. Refusals land in `promotion_ocr_refused.json`.

Duplicate detection is scoped **per year**, matching the text-layer parser: the
source genuinely re-uses recalls across sittings, and someone drilling 2024
should still see a question that also appeared in 2018.

The trap worth knowing: these screenshots come from a question bank that shows
respondent percentages. A pink row reads **"Your Answer"** — some student's pick,
not the key. Only the green **"NN% Correct Answer"** row is authoritative. An
audit of all 41 confirmed every key matches the marker in its own image.

## Reviewer second opinions (step 4)

Every published question carries an independent review: the reviewer answers from
the stem and options *before* seeing the source's key, then writes a teaching
explanation. Disagreement is shown to the reader in its own colour and states the
split outright.

**The reviewer never overwrites `correctAnswer`.** The exam's key is what the exam
marks, and a reviewer is not the exam — so both are shown and the reader decides.
This is the same rule that governs the parser: surface a disagreement, never
silently resolve one.

The 167 recalls the source never answered ship as their own bank,
`promotion-unkeyed`, labelled reviewer-answered in its manifest description. A
recall too degraded to answer honestly — options missing so the real key cannot
be among them, a stem truncated past comprehension, a question resting entirely
on an absent image — is refused rather than force-fitted, and every one of those
refusals is counted in the merge output.

## Known limits

- **~200 recalls carry no answer key anywhere in the source.** They are
  excluded, not guessed. Pages 515–542 (2015) are the largest block: 76
  correctly-formatted questions whose keys are only implied by a prose
  paragraph.
- **Two screenshot recalls are recoverable by hand.** One ("Where is the thinnest
  part of the sclera?") has its stem and its keyed explanation split across two
  separate screenshots, so neither half carries a visible marker on its own. One
  transcription was refused as low-confidence. Both are listed in
  `promotion_ocr_refused.json`.
- **One transcribed key is contested at source** (2024, p61, herpes uveitis): the
  only marker is a handwritten tick, but the compiler wrote in the margin that it
  looks wrong. The record says so in its explanation.
- **Residual figure drift.** Four guards contain it: year/subspecialty headings
  terminate a span, spans are capped at one page, the lowest anchor inside a
  figure's span owns it, and every `Answer:`/`Agree` line registers a recall
  boundary (542 of them) so single-option recalls still stop a span even though
  they cannot be published. Measured misplacement fell from ~32% to ~20%, then
  again with the baseline rule; it is not zero.

  Two things measurement disproved, worth not re-litigating: page-crossing is
  **not** the fault line — same-page misplacement (13.6%) was statistically
  indistinguishable from cross-page (20.5%), so disabling cross-page binding
  would have deleted about four correct figures for every wrong one it removed.
  And confining a figure to the pages a question's own text occupies looked
  principled but stripped figures that were verifiably correct.

  When re-checking this, beware the standing false positive: images are
  content-deduplicated, so a filename's page is the *first* page that image
  appeared on. The document genuinely reuses photos across years. A distant page
  number is not by itself evidence of misplacement.
