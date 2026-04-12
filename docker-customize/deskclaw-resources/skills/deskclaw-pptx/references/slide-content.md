## 4. Content Page

Pick a subtype based on the content. Each content slide belongs to exactly ONE subtype:

### Subtypes

**Text** — Bullets, quotes, or short paragraphs
- Must still include icons or SVG shapes — never plain text only
```
|  SLIDE TITLE                          |
|  * Bullet point one                   |
|  * Bullet point two                   |
|  * Bullet point three                 |
```

**Mixed Media** — Two-column or half-bleed image + text
```
|  SLIDE TITLE                          |
|  Text content     |  [Image/Visual]   |
|  and bullets      |                   |
```

**Data Visualization** — Chart (SVG bar/progress/ring) + takeaways
- Must include data source
```
|  SLIDE TITLE                          |
|  [SVG Chart]      |  Key Takeaway 1   |
|                   |  Key Takeaway 2   |
|                   Source: xxx          |
```

**Comparison** — Side-by-side columns or cards (A vs B, pros/cons)
```
|  SLIDE TITLE                          |
|  ┌─ Option A ─┐  ┌─ Option B ─┐      |
|  │  Detail 1  │  │  Detail 1  │      |
|  └────────────┘  └────────────┘      |
```

**Timeline / Process** — Steps with arrows, journey, phases
```
|  SLIDE TITLE                          |
|  [1] ──→ [2] ──→ [3] ──→ [4]         |
|  Step    Step    Step    Step          |
```

**Image Showcase** — Hero image, gallery, visual-first layout
```
|  SLIDE TITLE                          |
|  ┌────────────────────────────────┐   |
|  │         [Hero Image]           │   |
|  └────────────────────────────────┘   |
|  Caption or supporting text           |
```

### Font Size Hierarchy

| Element | Recommended Size | Notes |
|---------|-----------------|-------|
| Slide Title | 36-44px | Bold, top of slide |
| Section Header | 20-24px | Bold, for sub-sections within slide |
| Body Text | 14-16px | Regular weight, left-aligned |
| Captions / Source | 10-12px | Muted color, smallest text |
| Stat Callout | 60-72px | Large bold numbers for key statistics |

**Key Principles:**
1. **Left-align body text** — never center paragraphs or bullet lists
2. **Size contrast** — title must be 36pt+ to stand out from 14-16pt body
3. **Visual elements required** — every content slide must have at least one non-text element
4. **Breathing room** — 0.5" minimum margins, 0.3-0.5" between content blocks

### Content Elements

1. **Slide Title** — Always required, top of slide
2. **Body Content** — Text, bullets, data, or comparisons based on subtype
3. **Visual Element** — Image, chart, icon, or SVG shape — always required
4. **Source / Caption** — When showing data or external content
5. **Page Number Badge** — **MANDATORY**

### Design Decisions

1. **Subtype**: Determine first — drives the entire layout
2. **Content Volume**: Dense → multi-column or smaller font; Light → larger elements with more whitespace
3. **Data vs Narrative**: Data-heavy → charts + stat callouts; Story-driven → images + quotes
4. **Variety**: Each content slide should use a different layout from the previous one
5. **Consistency**: Typography, colors, and spacing must match the rest of the presentation

### Workflow

1. **Analyze**: Content, determine subtype, plan layout
2. **Choose Layout**: Best fit for subtype and content volume
3. **Write Slide**: Use PptxGenJS. Use shapes for charts, decorative elements, icons. **MUST include page number badge.**
4. **Verify**: Generate preview as `slide-XX-preview.pptx`. Extract text with markitdown, verify all content present, no placeholder text, badge included.

---

