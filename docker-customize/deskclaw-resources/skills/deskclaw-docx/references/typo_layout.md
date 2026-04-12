## Page Layout

### Margins by Document Type

| Document Type | Top | Bottom | Left | Right | DXA Values |
|--------------|-----|--------|------|-------|------------|
| **Standard business** | 1 in | 1 in | 1 in | 1 in | 1440 all |
| **Academic (APA/MLA)** | 1 in | 1 in | 1 in | 1 in | 1440 all |
| **Thesis (binding)** | 1 in | 1 in | 1.5 in | 1 in | T/B:1440 L:2160 R:1440 |
| **Chinese 公文** | 37mm | 35mm | 28mm | 26mm | T:2098 B:1984 L:1588 R:1474 |
| **Narrow modern** | 0.75 in | 0.75 in | 0.75 in | 0.75 in | 1080 all |
| **Wide** | 1 in | 1 in | 2 in | 2 in | T/B:1440 L/R:2880 |

### Page Sizes

| Size | Width × Height | DXA Width × Height |
|------|---------------|-------------------|
| US Letter | 8.5 × 11 in | 12240 × 15840 |
| A4 | 210 × 297 mm | 11906 × 16838 |
| Legal | 8.5 × 14 in | 12240 × 20160 |
| A3 | 297 × 420 mm | 16838 × 23811 |

**Rule**: A4 for international audiences, Letter for US-only.

### Page Numbers

| Convention | Placement | Common In |
|-----------|-----------|-----------|
| Bottom center | Footer, centered | Academic, government |
| Bottom right | Footer, right-aligned | Business reports |
| "Page X of Y" | Footer, right-aligned | Contracts, legal |
| Bottom outside | Alternating L/R for odd/even | Books, bound reports |
| Chinese 公文 | Bottom center, format "-X-" | Government documents |

---


## Table Design

### Style Patterns

| Style | Description | When to Use |
|-------|------------|-------------|
| **Three-line (三线表)** | Top rule + header-bottom rule + bottom rule only, no vertical lines | Academic, scientific — gold standard |
| **Banded rows** | Alternating white/light-gray, no borders | Modern corporate |
| **Light grid** | Thin 0.5pt gray borders all cells | Business reports |
| **Header-accent** | Dark/colored header row, no other borders | Modern templates |
| **Full border** | All cells bordered | Financial tables, forms |

### Border Weights (OpenXML `w:sz` in eighths of a point)

| Visual | `Size` value | Points |
|--------|-------------|--------|
| Hairline | 2 | 0.25pt |
| Thin | 4 | 0.5pt |
| Medium | 8 | 1pt |
| Thick | 12 | 1.5pt |

### Cell Padding

- **Minimum**: 0.05 in (28 DXA) — too tight for most uses
- **Recommended**: 0.08-0.1 in (57-72 DXA) top/bottom, 0.1-0.15 in (72-108 DXA) left/right
- **Spacious**: 0.12 in (86 DXA) top/bottom, 0.19 in (137 DXA) left/right

### Header Row Best Practices

- Bold text, optionally SMALL CAPS
- Background: light gray (#F2F2F2) or dark with white text (#2F5496 + white)
- Repeat header row on each page (`w:tblHeader` on `w:trPr`)
- Right-align number columns, left-align text columns

---


## Color Schemes

### Corporate / Business

| Element | Hex | Notes |
|---------|-----|-------|
| Primary heading | #1F3864 | Dark navy, authoritative |
| Secondary heading | #2E75B6 | Medium blue |
| Body text | #333333 | Near-black (softer than #000) |
| Table header bg | #4472C4 | With white #FFFFFF text |
| Alternate row | #F2F2F2 | Subtle gray banding |
| Hyperlink | #0563C1 | Standard blue |

### Academic

All text **#000000** (black). Color only in figures/charts.

### Chinese Government (公文)

| Element | Color |
|---------|-------|
| All body text | Black (required) |
| 红头 agency name | Red #FF0000 |
| 红线 separator | Red #FF0000 |
| 公章 seal | Red |

### Accessibility

- Minimum contrast ratio 4.5:1 for normal text, 3:1 for large text (WCAG AA)
- Never use color as sole means of conveying information
- Ensure distinguishable in grayscale for printed documents

---


## Visual Hierarchy

### Heading Levels by Document Length

| Pages | Recommended Levels |
|-------|-------------------|
| 1-5 (memo, letter) | 1-2 levels |
| 5-20 (report) | 2-3 levels |
| 20-100 (long report) | 3-4 levels |
| 100+ (thesis) | 4-5 levels max |

### Numbering Systems

**Decimal (ISO 2145)** — technical, international:
```
1 → 1.1 → 1.1.1 → 1.1.1.1
```

**Traditional outline (US legal):**
```
I. → A. → 1. → a. → (1) → (a)
```

**Chinese government (公文):**
```
一、(黑体) → （一）(楷体) → 1.(仿宋加粗) → (1)(仿宋)
```

### Typography Emphasis

| Format | Use For | Avoid |
|--------|---------|-------|
| **Bold** | Key terms, headings, emphasis | Entire paragraphs |
| *Italic* | Titles, foreign words, mild emphasis | Long passages (hard to read) |
| Underline | Hyperlinks only (digital) | General emphasis (archaic) |
| SMALL CAPS | Legal defined terms, acronyms | Body text |
| ALL CAPS | Very short headings | Long text (reduces readability 15%) |

**CJK note**: Chinese/Japanese have no true italic. Use bold for emphasis.

### List Formatting

**Bullets** (unordered): `•` → `○` → `■` by level

**Numbers** (ordered): `1.` → `a.` → `i.` by level

- Indent each level 0.25-0.5 in (360-720 DXA)
- Hanging indent: number hangs, text aligns consistently
- Spacing between items: 2-4pt (less than paragraph spacing)

---


## Quick Reference Defaults

### Business Report (Safe Default)

| Parameter | Value | OpenXML |
|-----------|-------|---------|
| Body font | Calibri 11pt | sz="22", RunFonts Ascii="Calibri" |
| H1 | 18pt Bold Dark Blue | sz="36", Bold, Color="#1F3864" |
| H2 | 14pt Bold Dark Blue | sz="28", Bold |
| H3 | 12pt Bold Dark Blue | sz="24", Bold |
| Line spacing | 1.15 | line="276" lineRule="auto" |
| Para after | 8pt | after="160" |
| Margins | 1 in all | 1440 DXA all |
| Page size | Letter or A4 | 12240×15840 or 11906×16838 |
| Page numbers | Bottom right, 10pt | |

### Academic Paper (APA 7th)

| Parameter | Value | OpenXML |
|-----------|-------|---------|
| Font | Times New Roman 12pt | sz="24" |
| Line spacing | Double | line="480" lineRule="auto" |
| First-line indent | 0.5 in | ind firstLine="720" |
| Margins | 1 in all | 1440 DXA all |
| Page numbers | Top right | Header, right-aligned |

### Chinese Government (公文 GB/T 9704)

| Parameter | Value | OpenXML |
|-----------|-------|---------|
| Body font | 仿宋_GB2312 三号 | sz="32", EastAsia="FangSong_GB2312" |
| Title | 小标宋 二号 centered | sz="44" |
| L1 heading | 黑体 三号 | sz="32", EastAsia="SimHei" |
| L2 heading | 楷体 三号 | sz="32", EastAsia="KaiTi_GB2312" |
| Line spacing | Fixed 28pt | line="560" lineRule="exact" |
| Margins | T:37mm B:35mm L:28mm R:26mm | T:2098 B:1984 L:1588 R:1474 |
| Page size | A4 | 11906×16838 |
| Page numbers | Bottom center, 宋体 四号, "-X-" | sz="28" |
| Chars/line | 28 | |
| Lines/page | 22 | |
