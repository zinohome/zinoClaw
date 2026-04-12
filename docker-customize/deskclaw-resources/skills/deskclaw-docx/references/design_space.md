## 1. White Space & Breathing Room

### Why It Works

The human eye does not read continuously. It jumps in saccades, fixating on
small clusters of words. White space provides landing zones for these fixations
and gives the reader's peripheral vision a "frame" that makes each text block
feel manageable. When a page is packed to the edges, every glance returns more
text than working memory can buffer, triggering fatigue and avoidance.

Research on content density consistently shows:

- **60-70% content coverage** feels comfortable and professional.
- **80%+** starts to feel dense and bureaucratic.
- **90%+** feels oppressive -- the reader unconsciously rushes or skips.
- **Below 50%** feels wasteful or pretentious (unless intentional, like poetry).

Wider margins also carry cultural signals. Academic and luxury documents use
generous margins (1.25-1.5 inches). Internal memos and drafts use narrower
margins (0.75-1.0 inches). The margin width tells the reader how much care
went into the document before they read a single word.

Line spacing has a direct physiological basis: the eye must track back to the
start of the next line after each line break. If lines are too close, the eye
"slips" to the wrong line. If too far apart, the eye loses its sense of
continuity. The sweet spot is 120-145% of the font size.

**Rule of thumb: when in doubt, add more space, not less.**

### Good Example

```
Margins: 1 inch (1440 twips) all sides for business documents.
Line spacing: 1.15 (276 twips at 240 twips-per-line = 115%).
Paragraph spacing after: 8pt (160 twips) between body paragraphs.
```

```xml
<!-- Page margins: 1 inch = 1440 twips on all sides -->
<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"
         w:header="720" w:footer="720" w:gutter="0"/>

<!-- Body paragraph: 1.15 line spacing, 8pt after -->
<w:pPr>
  <w:spacing w:after="160" w:line="276" w:lineRule="auto"/>
</w:pPr>
```

This produces a page where content occupies roughly 65% of the area. The
reader sees clear top/bottom breathing room, and paragraphs are distinct
without feeling disconnected.

```
  Page layout (good):
  +----------------------------------+
  |           1" margin              |
  |   +------------------------+    |
  |   | Heading                |    |
  |   |                        |    |
  |   | Body text here with    |    |
  |   | comfortable spacing    |    |
  |   | between lines.         |    |
  |   |                        |    |  <- visible gap between paragraphs
  |   | Another paragraph of   |    |
  |   | body text follows.     |    |
  |   |                        |    |
  |   +------------------------+    |
  |           1" margin              |
  +----------------------------------+
```

### Bad Example

```xml
<!-- Cramped margins: 0.5 inch = 720 twips -->
<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"
         w:header="360" w:footer="360" w:gutter="0"/>

<!-- No paragraph spacing, single line spacing -->
<w:pPr>
  <w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
</w:pPr>
```

This fills ~85% of the page. Text runs edge-to-edge with no visual rest stops.
The reader sees a wall of text.

```
  Page layout (bad):
  +----------------------------------+
  | Heading                          |
  | Body text crammed right up to    |
  | the margins with no spacing      |
  | between lines or paragraphs.     |
  | Another paragraph starts here    |
  | and the reader cannot tell where |
  | one idea ends and another begins |
  | because everything blurs into a  |
  | single dense block of text.      |
  +----------------------------------+
```

### Quick Test

1. Zoom out to 50% in your document viewer. If you cannot see clear "channels"
   of white between text blocks, the spacing is too tight.
2. Print a test page. Hold it at arm's length. The text area should look like
   a rectangle floating in white, not filling the page.
3. Check: is the line spacing value at least 264 (`w:line` for 1.1x) for body
   text? If it is 240 (single), it is too tight for anything over 10pt.

---


## 3. Proximity & Grouping

### Why It Works

The Gestalt principle of proximity: items that are close together are perceived
as belonging to the same group. In document typography, this means a heading
must be **closer to the content it introduces** than to the content above it.

If a heading sits equidistant between two paragraphs, it looks orphaned -- the
reader's eye does not know if it belongs to the text above or below. The fix
is asymmetric spacing: **large space before the heading, small space after**.

The recommended ratio is 2:1 or 3:1 (space-before : space-after).

This same principle applies to:
- **List items**: spacing between items should be less than spacing between
  paragraphs. Items in a list are a group and should visually cluster.
- **Captions**: a figure caption should be close to its figure, not floating
  in the middle between the figure and the next paragraph.
- **Table titles**: the title sits close above the table, with more space
  separating the title from preceding text.

### Good Example

```xml
<!-- H2: 18pt before, 6pt after (3:1 ratio) -->
<w:pPr>
  <w:pStyle w:val="Heading2"/>
  <w:spacing w:before="360" w:after="120"/>
</w:pPr>

<!-- Body paragraph: 0pt before, 8pt after -->
<w:pPr>
  <w:spacing w:before="0" w:after="160"/>
</w:pPr>

<!-- List item: 0pt before, 2pt after (tight grouping) -->
<w:pPr>
  <w:pStyle w:val="ListParagraph"/>
  <w:spacing w:before="0" w:after="40"/>
</w:pPr>
```

```
  Proximity (good):

  ...end of previous section text.
                                        <- 18pt gap (w:before="360")
  ## Section Heading
                                        <- 6pt gap (w:after="120")
  First paragraph of new section
  continues here with content.
                                        <- 8pt gap (w:after="160")
  Second paragraph follows.

  The heading clearly "belongs to" the text below it.
```

```
  List grouping (good):

  Consider these factors:
    - First item                        <- 2pt gap between items
    - Second item                       <- items cluster as a group
    - Third item
                                        <- 8pt gap after list
  The next paragraph starts here.
```

### Bad Example

```xml
<!-- H2: 12pt before, 12pt after (1:1 ratio -- orphaned heading) -->
<w:pPr>
  <w:pStyle w:val="Heading2"/>
  <w:spacing w:before="240" w:after="240"/>
</w:pPr>

<!-- List item: same spacing as body (10pt after) -->
<w:pPr>
  <w:pStyle w:val="ListParagraph"/>
  <w:spacing w:before="0" w:after="200"/>
</w:pPr>
```

```
  Proximity (bad):

  ...end of previous section text.
                                        <- 12pt gap
  ## Section Heading
                                        <- 12pt gap (same!)
  First paragraph of new section.

  The heading floats between sections. It is unclear what it belongs to.
```

```
  List grouping (bad):

  Consider these factors:
                                        <- 10pt gap
    - First item
                                        <- 10pt gap (same as paragraphs)
    - Second item
                                        <- 10pt gap
    - Third item
                                        <- 10pt gap
  Next paragraph.

  The list does not feel like a group. Each item looks like a
  separate paragraph that happens to have a bullet.
```

### Quick Test

1. **Cover test**: cover the heading text. Looking only at the whitespace,
   can you tell which block of text the heading belongs to? If the gaps above
   and below are equal, the answer is "no."
2. **Number check**: `w:before` on headings should be at least 2x `w:after`.
   Common good values: before=360 / after=120, or before=240 / after=80.
3. **List check**: `w:after` on list items should be less than half of
   `w:after` on body paragraphs. If body uses 160, list items should use
   40-60.

---

