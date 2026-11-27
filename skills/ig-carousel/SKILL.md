---
name: ig-carousel
description: >-
  Create an Instagram carousel with a strong cover, clear slide-by-slide copy,
  accessibility text, and a cohesive visual system. Can render 1080x1350 photo-led
  JPG slides and review PDFs with the bundled Pillow tool. Use when the user asks
  for a carousel, slides, a swipe post, or a list/sequence that needs re-reading.
---

# ig-carousel

A carousel is useful when an idea benefits from sequence, comparison, or being
saved and re-read. Every swipe must repay the viewer's attention. Do not split a
caption into slides just to fill a template.

## When to use it instead of a Reel

Use a carousel when the idea has **sequence and needs to be re-read**: steps, a
framework with parts, a before and after, or a list worth saving. Use a Reel
when motion, a face, or a payoff that has to be seen happening is central.

If the idea is one claim, it may work better as a single post or a Reel. Say so
instead of stretching it.

## Structure

Aim for 6 to 10 slides. Use fewer when the idea is complete sooner; never add
filler. A useful default is:

```
1         COVER     one clear promise or question; short enough to read at a glance
2         STAKE     why this matters, with enough context to stand alone
3 to N-2  ONE IDEA PER SLIDE; a short headline plus concise supporting copy
N-1       RECAP     a checklist, summary, or practical takeaway worth saving
LAST      CTA       one action, relevant to the post
```

The structure is a starting point, not a rule. A slide may combine recap and
CTA if a separate slide would be repetitive.

## Slide copy rules

- **Lead with a useful promise, not clickbait.** Keep the cover focused on one
  idea. A short headline is easier to scan in the grid and on a phone.
- **Make slide two work on its own.** It may be the first frame shown to someone
  who has already seen the cover.
- **One idea per slide.** Prefer a headline of 3 to 7 words and up to about 25
  words of supporting copy. Split or edit a paragraph rather than shrinking it
  to fit.
- **Use concrete language.** Add a real example, number, or action only when it
  is supported by the source material. Never invent outcomes, client stories,
  prices, features, or guarantees.
- **Make the recap self-contained.** A viewer should understand it without
  reading every earlier slide.
- **Use one relevant CTA.** Do not stack save, share, comment, follow, and DM
  requests on the same closing slide.
- **Write alt text.** Describe the cover's subject and message; do not repeat a
  keyword list. Provide slide-by-slide alt text when requested or needed for
  the handoff.

## Visual direction

Start from the user's actual identity: use supplied logo files, palette, and
fonts when available. Never invent or redraw an official-looking logo. If no
logo file is available, use a restrained typographic wordmark and label it as
such. Keep the layout recognizable across the deck without making every slide
the same stack of cards.

- Build portrait at **1080 × 1350 px (4:5)**. Keep text and essential details
  away from the edges; preview the cover in both the feed and profile-grid crop.
- Use one dominant text color, one or two accents, and quiet neutrals. Maintain
  strong contrast between type and background, including over photography.
- Use at most two complementary type families. Make headings, body copy, and
  labels visibly distinct; body text must still read on a phone without zooming.
- Let photography support the idea: alternate full-bleed, split, and smaller
  image treatments with clean editorial layouts. Do not force a photo onto
  every slide if it harms legibility or meaning.
- Use licensed/user-owned images. If conceptual generated imagery is used,
  don't present it as a real customer, a testimonial, a result, or a screenshot
  of a real platform. Never fabricate a Google profile, analytics, reviews, or
  product UI.
- Keep stable elements (palette, margins, footer/handle, numbering) consistent;
  vary scale, crop, and composition for visual rhythm.
- Review the deck at phone size. Fix clipped text, awkward wraps, low contrast,
  repetitive imagery, and any slide that looks like a generic quote-card pack.

## Preparing the copy

Write the slide-by-slide copy first so the user can review it before rendering.
Then prepare the caption as a separate deliverable: it should add context or a
useful next step rather than repeat every slide. Run the text through
`/ig-human` when available. Verify every factual claim and any current pricing
against an authoritative source before publication.

Use this Markdown structure for renderable source. Hard-break backslashes after
bold slide headings are accepted; normal Markdown line breaks also work.

```markdown
## Carrusel 1 · A useful title

**Portada, texto alternativo:** A concise description of the cover.

1. **Portada**\
   **A clear cover question?**\
   One short line that sets the promise.

2. **The useful point**\
   Explain one thing in plain language.

3. **Cierre**\
   One next step that fits the content.

**Caption**\
A caption that adds context and a single CTA.
```

## Rendering the files

The bundled renderer makes photo-led 1080 × 1350 JPEG slides plus per-carousel
PDF previews, captions, alt text, and a short README. Install its only
third-party dependency:

```bash
python3 -m pip install -r skills/ig-carousel/requirements.txt
```

Copy `brand.example.json`, replace the brand name, handle, palette, photo paths,
and optional font paths. The photos list must have one image for each carousel
in the Markdown file. Asset and font paths in the JSON are relative to that
JSON file, or may be absolute.

```bash
python3 skills/ig-carousel/render_carousel.py \
  entregables/carruseles.md \
  --brand entregables/brand.json \
  --out .cache/carruseles
```

The renderer writes a folder per carousel with numbered JPGs, `preview.pdf`,
`caption.txt`, and `alt-text.txt`. It also records that the wordmark is
text-only; it does not replace an official logo. Keep generated output outside
Git unless the project explicitly versions its final assets.

## Quality check

1. Run the parser/render tests:

   ```bash
   python3 -m unittest discover -s skills/ig-carousel -p 'test_*.py'
   ```

2. Confirm the slide count matches the copy, each JPG is 1080 × 1350, and each
   preview opens. Check that the caption and alt text are non-empty and that no
   caption or Markdown artifacts leaked onto a slide.
3. Review a contact sheet and each cover, recap, and closing slide at phone
   size. Look for clipping, weak contrast, awkward crops, repeated images, and
   text competing with the photo. Fix source copy or layout; do not hide
   overflow by silently dropping words.
4. Recheck claims, prices, links, handle, rights to imagery, and spelling.

Show the copy and a visual preview for approval when appropriate. **Never
publish.** Upload to a private review location only when explicitly requested;
otherwise hand the files to the user to post.
