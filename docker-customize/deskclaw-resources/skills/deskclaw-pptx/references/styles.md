# Style Recipes

The same design can be rendered in 4 distinct visual styles by adjusting corner radius (`rectRadius`) and spacing. Choose the style recipe that fits the presentation tone.

> **Unit note**: PptxGenJS uses inches. Slide dimensions are 10" x 5.625" (LAYOUT_16x9).

### Style Overview

| Style | Corner Radius | Spacing | Best For |
|-------|--------------|---------|----------|
| **Sharp & Compact** | 0 ~ 0.05" | Tight | Data-dense, tables, professional reports |
| **Soft & Balanced** | 0.08" ~ 0.12" | Moderate | Corporate, business presentations, general use |
| **Rounded & Spacious** | 0.15" ~ 0.25" | Relaxed | Product intros, marketing, creative showcases |
| **Pill & Airy** | 0.3" ~ 0.5" | Open | Brand showcases, launch events, premium presentations |

### Sharp & Compact

**Visual character**: Geometric, high information density, formal and serious.

| Category | Value (inches) | Notes |
|----------|---------------|-------|
| Corner radius — small | 0" | Full right angle |
| Corner radius — medium | 0.03" | Micro-rounded |
| Corner radius — large | 0.05" | Slight rounding |
| Element padding | 0.1" ~ 0.15" | Compact |
| Element gap | 0.1" ~ 0.2" | Compact |
| Page margin | 0.3" | Narrow |
| Block gap | 0.25" ~ 0.35" | Compact |

### Soft & Balanced

**Visual character**: Moderate rounding, comfortable whitespace, professional yet approachable.

| Category | Value (inches) | Notes |
|----------|---------------|-------|
| Corner radius — small | 0.05" | Slight rounding |
| Corner radius — medium | 0.08" | Medium rounding |
| Corner radius — large | 0.12" | Larger rounding |
| Element padding | 0.15" ~ 0.2" | Moderate |
| Element gap | 0.15" ~ 0.25" | Moderate |
| Page margin | 0.4" | Standard |
| Block gap | 0.35" ~ 0.5" | Moderate |

### Rounded & Spacious

**Visual character**: Large corners, generous whitespace, friendly and modern.

| Category | Value (inches) | Notes |
|----------|---------------|-------|
| Corner radius — small | 0.1" | Medium rounding |
| Corner radius — medium | 0.15" | Large rounding |
| Corner radius — large | 0.25" | Very large rounding |
| Element padding | 0.2" ~ 0.3" | Relaxed |
| Element gap | 0.25" ~ 0.4" | Relaxed |
| Page margin | 0.5" | Wide |
| Block gap | 0.5" ~ 0.7" | Relaxed |

### Pill & Airy

**Visual character**: Full pill-shaped corners, abundant whitespace, light and open feel, strong brand presence.

| Category | Value (inches) | Notes |
|----------|---------------|-------|
| Corner radius — small | 0.2" | Large rounding |
| Corner radius — medium | 0.3" | Pill shape |
| Corner radius — large | 0.5" | Full pill |
| Element padding | 0.25" ~ 0.4" | Open |
| Element gap | 0.3" ~ 0.5" | Open |
| Page margin | 0.6" | Wide |
| Block gap | 0.6" ~ 0.9" | Open |

### Component Style Mapping

| Component | Sharp | Soft | Rounded | Pill |
|-----------|-------|------|---------|------|
| **Button / Tag** | rectRadius: 0 | rectRadius: 0.05 | rectRadius: 0.1 | rectRadius: 0.2 |
| **Card / Container** | rectRadius: 0.03 | rectRadius: 0.1 | rectRadius: 0.2 | rectRadius: 0.3 |
| **Image Container** | rectRadius: 0 | rectRadius: 0.08 | rectRadius: 0.15 | rectRadius: 0.25 |
| **Input Field** | rectRadius: 0 | rectRadius: 0.05 | rectRadius: 0.1 | rectRadius: 0.2 |
| **Badge** | rectRadius: 0.02 | rectRadius: 0.05 | rectRadius: 0.08 | rectRadius: 0.15 |
| **Avatar Frame** | rectRadius: 0 | rectRadius: 0.1 | rectRadius: 0.2 | rectRadius: 0.5 (circle) |

#### PptxGenJS Corner Radius Examples

```javascript
// Sharp style card
slide.addShape("rect", {
  x: 0.5, y: 1, w: 4, h: 2.5,
  fill: { color: "F5F5F5" },
  rectRadius: 0.03
});

// Rounded style card
slide.addShape("rect", {
  x: 0.5, y: 1, w: 4, h: 2.5,
  fill: { color: "F5F5F5" },
  rectRadius: 0.2
});

// Pill style button (height 0.4", rectRadius 0.2" = perfect pill)
slide.addShape("rect", {
  x: 3, y: 4, w: 2, h: 0.4,
  fill: { color: "4A90D9" },
  rectRadius: 0.2
});
```

### Mixing Rules

#### 1. Outer container corner >= inner element corner

```javascript
// Correct: outer > inner
card:   rectRadius: 0.2
button: rectRadius: 0.1

// Wrong: inner > outer → visual overflow effect
card:   rectRadius: 0.1
button: rectRadius: 0.2
```

#### 2. Information density drives spacing

| Zone Type | Recommended Style |
|-----------|------------------|
| Data display zone | Sharp / Soft (compact spacing) |
| Content browsing zone | Rounded / Pill (relaxed spacing) |
| Title zone | Soft / Rounded (moderate spacing) |

#### 3. Corner radius vs element height

| Element Height | Sharp | Soft | Rounded | Pill |
|---------------|-------|------|---------|------|
| Small (< 0.3") | 0" | 0.03" | 0.08" | height/2 |
| Medium (0.3" ~ 0.6") | 0.02" | 0.05" | 0.12" | height/2 |
| Large (0.6" ~ 1.2") | 0.03" | 0.08" | 0.2" | 0.3" |
| Extra large (> 1.2") | 0.05" | 0.12" | 0.25" | 0.4" |

> **Pill tip**: For a perfect pill shape, set `rectRadius = element height / 2`

### Typography Scale (PPT)

| Usage | Size (pt) | Notes |
|-------|-----------|-------|
| Annotations / Sources | 10 ~ 12 | Minimum readable size |
| Body / Description | 14 ~ 16 | Standard body |
| Subtitle | 18 ~ 22 | Secondary heading |
| Title | 28 ~ 36 | Page title |
| Large Title | 44 ~ 60 | Cover / section title |
| Data Callout | 60 ~ 96 | Key number display |

### Spacing Scale (PPT)

Based on 10" x 5.625" slide dimensions:

| Usage | Recommended (inches) |
|-------|---------------------|
| Icon-to-text gap | 0.08" ~ 0.15" |
| List item spacing | 0.15" ~ 0.25" |
| Card inner padding | 0.2" ~ 0.4" |
| Element group gap | 0.3" ~ 0.5" |
| Page safe margin | 0.4" ~ 0.6" |
| Major block gap | 0.5" ~ 0.8" |

### Quick Selection Guide

| Presentation Type | Recommended Style | Reason |
|------------------|------------------|--------|
| Finance / Data reports | Sharp & Compact | High density, serious and precise |
| Corporate / Business | Soft & Balanced | Balances professionalism and approachability |
| Product intro / Marketing | Rounded & Spacious | Modern feel, friendly |
| Launch events / Brand | Pill & Airy | Premium feel, visual impact |
| Training / Education | Soft / Rounded | Clear, readable, friendly |
| Tech sharing | Sharp / Soft | Professional, information-dense |

