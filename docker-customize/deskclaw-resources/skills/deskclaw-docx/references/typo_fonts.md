## Font Pairing

### Recommended Pairs

| Headings | Body | Style | Best For |
|----------|------|-------|----------|
| Calibri Light | Calibri | Modern sans | Corporate reports |
| Aptos | Aptos | Office 365 default | Modern business docs |
| Cambria | Calibri | Serif + sans | Academic-corporate hybrid |
| Times New Roman | Times New Roman | Traditional serif | Academic, legal |
| Arial | Arial | Clean sans | Memos, internal docs |
| Georgia | Garamond | Classical serif pair | Formal reports |

### Rules

- **Limit**: 2 font families max (3 if CJK mixed)
- **Contrast**: Pair serif with sans-serif, OR use weight contrast within one family
- **Consistency**: Same font for all body text, same font for all headings

---


## Font Sizes by Document Type

| Document Type | Body | H1 | H2 | H3 | Footnotes |
|--------------|------|----|----|----|----|
| **Business report** | 11pt | 18-20pt | 14-16pt | 12-13pt bold | 9pt |
| **Business letter** | 11-12pt | — | — | — | 9-10pt |
| **Memo** | 11pt | 14pt bold | 12pt bold | 11pt bold | 9pt |
| **Contract / Legal** | 12pt | 14pt bold caps | 12pt bold | 12pt bold | 10pt |
| **Academic (APA 7)** | 12pt | 12pt bold center | 12pt bold left | 12pt bold italic | 10pt |
| **Resume / CV** | 10-11pt | 14-16pt | 12pt bold | 11pt bold | 8-9pt |
| **Chinese 公文** | 三号(16pt) | 二号(22pt) | 三号(16pt) | 四号(14pt) | 小四(12pt) |

### OpenXML `w:sz` Values (half-points)

| Point Size | `w:sz` Val | Common Use |
|-----------|-----------|------------|
| 9pt | 18 | Footnotes, captions |
| 10pt | 20 | Compact body text |
| 10.5pt (五号) | 21 | CJK body small |
| 11pt | 22 | Standard body (Calibri) |
| 12pt (小四) | 24 | Standard body (TNR), CJK |
| 14pt (四号) | 28 | CJK body, subheading |
| 16pt (三号) | 32 | CJK heading, western H2 |
| 18pt (小二) | 36 | Western H1 |
| 22pt (二号) | 44 | CJK document title |
| 26pt (一号) | 52 | Large title |

---


## Line Spacing

| Spacing | OpenXML `w:spacing line` | When to Use |
|---------|--------------------------|-------------|
| Single (1.0) | `line="240"` lineRule="auto" | Tables, footnotes, captions |
| 1.08 (MS default) | `line="259"` lineRule="auto" | Modern Office documents |
| 1.15 | `line="276"` lineRule="auto" | Business reports — best general default |
| 1.5 | `line="360"` lineRule="auto" | Some academic, drafts for markup |
| Double (2.0) | `line="480"` lineRule="auto" | APA/MLA manuscripts, legal briefs |
| Fixed 28pt | `line="560"` lineRule="exact" | Chinese 公文 (GB/T 9704) |

**`lineRule` values**: `auto` = proportional (240 = 1 line), `exact` = fixed height, `atLeast` = minimum.

---


## Paragraph Spacing

| Element | Space Before (DXA) | Space After (DXA) |
|---------|-------------------|-------------------|
| Body paragraph | 0 | 120-160 (6-8pt) |
| Heading 1 | 480 (24pt) | 120-240 |
| Heading 2 | 360 (18pt) | 120 |
| Heading 3 | 240 (12pt) | 80-120 |
| List items | 0 | 40-80 (2-4pt) |
| Block quote | 120-240 | 120-240 |
| Table/Figure caption | 240 | 240 |

**Principle**: Space before a heading > space after, so heading visually "belongs to" content below (2:1 or 3:1 ratio).

---

