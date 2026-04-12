# Slide Page Types

Classify **every slide** as **exactly one** of these 5 types:

## 1. Cover Page

- **Use for**: Opening + tone setting
- **Content**: Big title, subtitle/presenter, date/occasion, strong background/motif

### Layout Options

**Asymmetric Left-Right Layout**
- Text concentrated on one side, image on the opposite
- Best for: Corporate presentations, product launches, professional reports
```
|  Title & Subtitle  |    Visual/Image    |
|  Description       |                    |
```

**Center-Aligned Layout**
- Content centered with background image
- Best for: Inspirational talks, event presentations, creative pitches
```
|                                        |
|           [Background Image]           |
|              MAIN TITLE                |
|              Subtitle                  |
|                                        |
```

### Font Size Hierarchy

| Element | Recommended Size | Ratio to Base |
|---------|-----------------|---------------|
| Main Title | 72-120px | 3x-5x |
| Subtitle | 28-40px | 1.5x-2x |
| Supporting Text | 18-24px | 1x (base) |
| Meta Info (date, name) | 14-18px | 0.7x-1x |

**Key Principles:**
1. **Dramatic Contrast**: Main title should be at least 2-3x larger than subtitle
2. **Visual Anchor**: The largest text becomes the focal point
3. **Readable Hierarchy**: Viewers should instantly understand what's most important
4. **Avoid Similarity**: Never let adjacent text elements be within 20% of each other's size

### Content Elements

1. **Main Title** — Always required, largest font
2. **Subtitle** — When additional context is needed (clearly smaller than title)
3. **Icons** — When they reinforce the theme
4. **Date/Event Info** — When relevant (smallest text)
5. **Company/Brand Logo** — When representing an organization
6. **Presenter Name** — For keynotes (small, subtle)

### Design Decisions

Consider: Purpose (corporate/educational/creative), Audience, Tone, Content Volume, Visual Assets needed.

### Workflow

1. **Analyze**: Understand topic, audience, purpose
2. **Choose Layout**: Select based on content
3. **Write Slide**: Use PptxGenJS. Use shapes and SVG elements for visual interest.
4. **Verify**: Generate preview as `slide-XX-preview.pptx`. Extract text with `python -m markitdown slide-XX-preview.pptx`, verify all content present and no placeholder text remains.

---

