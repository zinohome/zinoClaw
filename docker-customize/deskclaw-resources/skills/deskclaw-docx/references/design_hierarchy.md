## 6. Visual Hierarchy & Flow

### Why It Works

A well-designed document guides the reader's eye in a predictable path:
title at the top, subtitle below it, section headings as signposts, body text
as the main content, footnotes and captions as supporting details. This flow
mirrors reading priority -- the most important information is the most visually
prominent.

Each level in the hierarchy must be **distinguishable from its adjacent
levels**. It is not enough for H1 to differ from body text; H1 must also
clearly differ from H2, and H2 from H3. If any two adjacent levels are too
similar, the hierarchy collapses at that point.

Effective hierarchy uses **multiple simultaneous signals**:

| Level    | Size  | Weight  | Color   | Spacing above |
|----------|-------|---------|---------|---------------|
| Title    | 26pt  | Bold    | #1F3864 | 0 (top)       |
| Subtitle | 15pt  | Regular | #4472C4 | 4pt           |
| H1       | 20pt  | Bold    | #1F3864 | 24pt          |
| H2       | 16pt  | Bold    | #1F3864 | 18pt          |
| H3       | 13pt  | Bold    | #1F3864 | 12pt          |
| Body     | 11pt  | Regular | #333333 | 0pt           |
| Caption  | 9pt   | Italic  | #666666 | 4pt           |
| Footnote | 9pt   | Regular | #666666 | 0pt           |

Notice how each level differs from its neighbors on at least two dimensions
(size + weight, or size + color, or weight + style). Single-dimension
differences are fragile and can be missed.

**Section breaks** create rhythm in long documents. A page break before each
major section (H1) gives the reader a mental reset. Within sections, consistent
heading + body patterns create a predictable cadence that makes long documents
less intimidating.

### Good Example

```xml
<!-- Title: large, bold, navy, centered -->
<w:style w:type="paragraph" w:styleId="Title">
  <w:pPr>
    <w:jc w:val="center"/>
    <w:spacing w:after="80"/>
  </w:pPr>
  <w:rPr>
    <w:b/>
    <w:sz w:val="52"/>
    <w:color w:val="1F3864"/>
  </w:rPr>
</w:style>

<!-- Subtitle: medium, regular weight, lighter blue, centered -->
<w:style w:type="paragraph" w:styleId="Subtitle">
  <w:pPr>
    <w:jc w:val="center"/>
    <w:spacing w:after="320"/>
  </w:pPr>
  <w:rPr>
    <w:sz w:val="30"/>
    <w:color w:val="4472C4"/>
  </w:rPr>
</w:style>

<!-- H1: page break before, large bold navy -->
<w:style w:type="paragraph" w:styleId="Heading1">
  <w:pPr>
    <w:pageBreakBefore/>
    <w:keepNext/>
    <w:keepLines/>
    <w:spacing w:before="480" w:after="160"/>
    <w:outlineLvl w:val="0"/>
  </w:pPr>
  <w:rPr>
    <w:b/>
    <w:sz w:val="40"/>
    <w:color w:val="1F3864"/>
  </w:rPr>
</w:style>

<!-- Caption: small, italic, gray -->
<w:style w:type="paragraph" w:styleId="Caption">
  <w:pPr>
    <w:spacing w:before="80" w:after="200"/>
  </w:pPr>
  <w:rPr>
    <w:i/>
    <w:sz w:val="18"/>
    <w:color w:val="666666"/>
  </w:rPr>
</w:style>
```

```
  Visual flow (good):

  +----------------------------------+
  |                                  |
  |     ANNUAL REPORT 2025           |  <- Title: 26pt bold navy centered
  |     Acme Corporation             |  <- Subtitle: 15pt regular blue
  |                                  |
  |                                  |
  +----------------------------------+

  +----------------------------------+
  |                                  |
  |  1. Executive Summary            |  <- H1: 20pt bold navy (page break)
  |                                  |
  |  Body text introducing the       |  <- Body: 11pt regular gray
  |  main findings of the year.      |
  |                                  |
  |  1.1 Revenue Highlights          |  <- H2: 16pt bold navy
  |                                  |
  |  Revenue grew by 23% year        |  <- Body
  |  over year, driven by...         |
  |                                  |
  |  Figure 1: Revenue Growth        |  <- Caption: 9pt italic gray
  |                                  |
  +----------------------------------+

  Each level is immediately identifiable. The eye flows naturally
  from title -> heading -> body -> caption.
```

### Bad Example

```xml
<!-- All headings same color as body, minimal size difference -->
<w:style w:type="paragraph" w:styleId="Heading1">
  <w:rPr>
    <w:b/>
    <w:sz w:val="28"/>       <!-- 14pt -- only 3pt above body -->
    <w:color w:val="000000"/> <!-- same color as body -->
  </w:rPr>
</w:style>

<!-- Caption same size as body, not italic -->
<w:style w:type="paragraph" w:styleId="Caption">
  <w:rPr>
    <w:sz w:val="22"/>        <!-- same 11pt as body! -->
    <w:color w:val="000000"/> <!-- same color as body -->
  </w:rPr>
</w:style>

<!-- No page breaks between major sections -->
<!-- H1 has no pageBreakBefore, keepNext, or keepLines -->
```

Problems:
- H1 at 14pt is too close to body at 11pt (ratio 1.27 -- acceptable in
  isolation but with black color matching body, the hierarchy is weak).
- Caption is indistinguishable from body text.
- No page breaks means major sections bleed into each other with no
  visual rhythm.
- Everything is black, so color provides zero hierarchy signal.

### Quick Test

1. **The squint test**: blur your eyes while looking at a full page. You
   should see 3-4 distinct "weight levels" of gray. If the page looks like
   one uniform shade, the hierarchy is too flat.
2. **The scan test**: flip through pages quickly. Can you identify section
   boundaries in under one second per page? If yes, the visual hierarchy is
   working. If pages blur together, you need stronger differentiation at H1.
3. **Adjacent level test**: for each heading level, check that it differs
   from the next level on at least 2 of: size, weight, color, style (italic).
   Single-dimension differences get lost.
4. **Rhythm test**: in a document over 10 pages, do major sections (H1) start
   on new pages? If not, long documents will feel like an undifferentiated
   stream. Add `w:pageBreakBefore` to Heading1.

---

## Summary: Decision Checklist

When you are unsure about a typographic choice, run through these checks:

| Principle | Question | If No... |
|-----------|----------|----------|
| White Space | Does the page have at least 30% white space? | Increase margins or spacing |
| Contrast | Can I count heading levels by squinting? | Increase size ratios (target 1.25x) |
| Proximity | Does each heading clearly belong to text below it? | Make space-before > space-after (2:1) |
| Alignment | Is English left-aligned and CJK justified? | Switch alignment mode |
| Repetition | Do all same-level elements use the same style? | Replace direct formatting with styles |
| Hierarchy | Can I see the document structure at arm's length? | Add more differentiation signals |

**When two principles conflict, prioritize in this order:**

1. **Readability** (white space, line spacing) -- always wins
2. **Hierarchy** (contrast, scale) -- readers must find what they need
3. **Consistency** (repetition) -- builds trust
4. **Aesthetics** (alignment, grouping) -- the finishing touch
