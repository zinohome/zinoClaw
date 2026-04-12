## 2. Table of Contents

- **Use for**: Navigation + expectation setting (3-5 sections)
- **Content**: Section list (optional icons / page numbers)

### Layout Options

**Numbered Vertical List** — Best for 3-5 sections, straightforward presentations
```
|  TABLE OF CONTENTS            |
|                                |
|  01  Section Title One         |
|  02  Section Title Two         |
|  03  Section Title Three       |
```

**Two-Column Grid** — Best for 4-6 sections, content-rich presentations
```
|  TABLE OF CONTENTS              |
|                                  |
|  01  Section One   02  Section Two  |
|      Description       Description  |
|  03  Section Three 04  Section Four |
```

**Sidebar Navigation** — Best for 3-5 sections, modern/corporate
```
| ▌01 |  Section Title One           |
| ▌02 |  Section Title Two           |
| ▌03 |  Section Title Three         |
```

**Card-Based** — Best for 3-4 sections, creative/modern
```
|  TABLE OF CONTENTS                    |
|  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  |
|  │ 01  │  │ 02  │  │ 03  │  │ 04  │  |
|  │Title│  │Title│  │Title│  │Title│  |
|  └─────┘  └─────┘  └─────┘  └─────┘  |
```

### Font Size Hierarchy

| Element | Recommended Size | Ratio to Base |
|---------|-----------------|---------------|
| Page Title ("Table of Contents" / "Agenda") | 36-44px | 2.5x-3x |
| Section Number | 28-36px | 2x-2.5x |
| Section Title | 20-28px | 1.5x-2x |
| Section Description | 14-16px | 1x (base) |

**Key Principles:**
1. **Clear Numbering**: Section numbers should be visually prominent — bold, accent color, or larger size
2. **Scannable Structure**: Viewer should scan all sections in 2-3 seconds
3. **Consistent Spacing**: Equal vertical spacing between sections
4. **Visual Markers**: Colored dots, lines, numbers, or icons to anchor each section
5. **Avoid Clutter**: Descriptions one line max or omit entirely

### Content Elements

1. **Page Title** — Always required ("Table of Contents", "Agenda", "Overview")
2. **Section Numbers** — Consistent format (01, 02... or I, II...)
3. **Section Titles** — Clear and concise
4. **Section Descriptions** — Optional one-line summaries
5. **Visual Separators** — SVG dividers or spacing
6. **Decorative Elements** — Subtle accent shapes
7. **Page Number Badge** — **MANDATORY**

### Design Decisions

1. **Section Count**: 3 → vertical list; 4-6 → grid or compact; 7+ → multi-column
2. **Description Length**: Long → vertical list; None → compact grid/cards
3. **Tone**: Corporate → numbered list; Creative → card-based; Academic → Roman numerals
4. **Consistency**: Match visual style of cover page

### Workflow

1. **Analyze**: Section list, count, presentation context
2. **Choose Layout**: Based on section count and content
3. **Plan Visual Hierarchy**: Numbering style, font sizes, spacing
4. **Write Slide**: Use PptxGenJS. Use shapes for decorative elements. **MUST include page number badge.**
5. **Verify**: Generate preview, extract text with markitdown, verify content and badge.

---

## 3. Section Divider

- **Use for**: Clear transitions between major parts
- **Content**: Section number + title (+ optional 1-2 line intro)

### Layout Options

**Bold Center** — Best for minimal, modern presentations
```
|                  02                    |
|           SECTION TITLE               |
|         Optional intro line           |
```

**Left-Aligned with Accent Block** — Best for corporate, structured presentations
```
| ████ |  02                            |
| ████ |  SECTION TITLE                 |
| ████ |  Optional intro line           |
```

**Split Background** — Best for high-contrast, dramatic transitions
```
| ██████████ |     SECTION TITLE        |
| ██  02  ██ |     Optional intro       |
| ██████████ |                          |
```

**Full-Bleed Background with Overlay** — Best for creative, bold presentations
```
| ████████████████████████████████████  |
| ████       large 02        █████████ |
| ████    SECTION TITLE      █████████ |
| ████████████████████████████████████  |
```

### Font Size Hierarchy

| Element | Recommended Size | Notes |
|---------|-----------------|-------|
| Section Number | 72-120px | Bold, accent color or semi-transparent |
| Section Title | 36-48px | Bold, clear, primary text color |
| Intro Text | 16-20px | Light weight, muted color, optional |

**Key Principles:**
1. **Dramatic Number**: Section number = most prominent visual element
2. **Strong Title**: Large but clearly secondary to the number
3. **Minimal Content**: Just number + title + optional one-liner
4. **Breathing Room**: Leave generous whitespace — dividers are pause moments

### Content Elements

1. **Section Number** — Always required. Format: `01`, `02`... or `I`, `II`... Match TOC style.
2. **Section Title** — Always required. Clear, concise.
3. **Intro Text** — Optional 1-2 line description.
4. **Decorative Elements** — SVG accent shapes (bars, lines, geometric blocks).
5. **Page Number Badge** — **MANDATORY**.

### Design Decisions

1. **Tone**: Corporate → accent block; Creative → full-bleed; Minimal → bold center
2. **Color**: Strong palette color for background/accent; high-contrast text
3. **Consistency**: Same divider style across all dividers in one presentation
4. **Contrast with content slides**: Visually distinct (different background color, more whitespace)

### Workflow

1. **Analyze**: Section number, title, optional intro
2. **Choose Layout**: Based on content and tone
3. **Write Slide**: Use PptxGenJS. Use shapes for decorative elements. **MUST include page number badge.**
4. **Verify**: Generate preview, extract text, verify content and badge.

---

