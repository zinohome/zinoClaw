## 2. Contrast & Scale

### Why It Works

The brain processes visual hierarchy through relative difference, not absolute
size. A 20pt heading above 11pt body text creates a clear "this is important"
signal. But if every heading is 20pt and every sub-heading is 19pt, the brain
cannot distinguish them -- they merge into the same level.

The key insight is **modular scale**: font sizes that grow by a consistent
ratio. This mirrors natural proportions and feels harmonious for the same
reason musical intervals do.

Common scales and their character:

| Ratio | Name           | Character                       | Example progression (from 11pt) |
|-------|----------------|---------------------------------|---------------------------------|
| 1.200 | Minor third    | Subtle, refined                 | 11 → 13.2 → 15.8 → 19.0       |
| 1.250 | Major third    | Balanced, professional          | 11 → 13.75 → 17.2 → 21.5      |
| 1.333 | Perfect fourth | Strong, authoritative           | 11 → 14.7 → 19.5 → 26.0       |
| 1.414 | Augmented 4th  | Dramatic, presentation-style    | 11 → 15.6 → 22.0 → 31.1       |

For most business documents, 1.25 (major third) works best:

```
Body  = 11pt  (w:sz="22")
H3    = 13pt  (w:sz="26")   -- 11 * 1.25 ≈ 13.75, round to 13
H2    = 16pt  (w:sz="32")   -- 13 * 1.25 ≈ 16.25, round to 16
H1    = 20pt  (w:sz="40")   -- 16 * 1.25 = 20
```

Beyond size, **weight contrast** creates hierarchy without consuming vertical
space. Regular (400) vs Bold (700) is visible at any size. Semi-bold (600) vs
Regular is subtle and best avoided unless you also vary size or color.

**Color contrast** adds a third dimension. Dark blue headings (#1F3864) against
softer dark gray body text (#333333) signals "heading" without needing a huge
size jump. Pure black (#000000) body text is harsher than necessary on white
backgrounds -- #333333 or #2D2D2D reduces glare without losing legibility.

### Good Example

```xml
<!-- H1: 20pt, bold, dark navy -->
<w:rPr>
  <w:b/>
  <w:sz w:val="40"/>
  <w:color w:val="1F3864"/>
</w:rPr>

<!-- H2: 16pt, bold, dark navy -->
<w:rPr>
  <w:b/>
  <w:sz w:val="32"/>
  <w:color w:val="1F3864"/>
</w:rPr>

<!-- H3: 13pt, bold, dark navy -->
<w:rPr>
  <w:b/>
  <w:sz w:val="26"/>
  <w:color w:val="1F3864"/>
</w:rPr>

<!-- Body: 11pt, regular, dark gray -->
<w:rPr>
  <w:sz w:val="22"/>
  <w:color w:val="333333"/>
</w:rPr>
```

```
  Visual hierarchy (good):

  [████████████████████]        <- H1: 20pt bold navy (clearly dominant)
                                   (generous space)
  [██████████████]              <- H2: 16pt bold navy (distinct step down)
                                   (moderate space)
  [████████████]                <- H3: 13pt bold navy (smaller but still bold)
  [░░░░░░░░░░░░░░░░░░░░░░]    <- Body: 11pt regular gray
  [░░░░░░░░░░░░░░░░░░░░░░]
  [░░░░░░░░░░░░░░░░░░░░░░]
```

Each level is visually distinct from its neighbors. You can identify the
hierarchy even in peripheral vision.

### Bad Example

```xml
<!-- H1: 14pt bold black -->
<w:rPr>
  <w:b/>
  <w:sz w:val="28"/>
  <w:color w:val="000000"/>
</w:rPr>

<!-- H2: 13pt bold black -->
<w:rPr>
  <w:b/>
  <w:sz w:val="26"/>
  <w:color w:val="000000"/>
</w:rPr>

<!-- H3: 12pt bold black -->
<w:rPr>
  <w:b/>
  <w:sz w:val="24"/>
  <w:color w:val="000000"/>
</w:rPr>

<!-- Body: 12pt regular black -->
<w:rPr>
  <w:sz w:val="24"/>
  <w:color w:val="000000"/>
</w:rPr>
```

Problems:
- H3 (12pt bold) and body (12pt regular) differ only by weight -- too subtle.
- H1 (14pt) to H2 (13pt) is a 1pt step -- invisible at reading distance.
- Everything is pure black so color provides no differentiating signal.
- The ratio between levels is ~1.07, far too flat.

### Quick Test

1. **The squint test**: blur your eyes or step back from the screen. Can you
   count the number of heading levels? If two levels merge, their contrast
   is insufficient.
2. **Ratio check**: divide each heading size by the next smaller size. If any
   ratio is below 1.15, the levels will look too similar.
3. **Color check**: do headings look distinct from body text when you glance
   at the page? If everything is the same color, you are relying solely on
   size/weight, which limits your hierarchy to ~3 effective levels.

---

