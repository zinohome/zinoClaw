# Fonts & Chinese Localization


### Recommended Fonts

| Language | Default Font | Alternatives |
|----------|-------------|--------------|
| **Chinese** | Microsoft YaHei | — |
| **English** | Arial | Georgia, Calibri, Cambria, Trebuchet MS |

- For mixed Chinese-English content: use Microsoft YaHei for Chinese, the chosen font for English
- Prefer system fonts for cross-platform compatibility
- Titles and body text can use different font pairings (e.g. Georgia + Calibri)

### Recommended Font Pairings

| Header Font | Body Font |
|-------------|-----------|
| Georgia | Calibri |
| Arial Black | Arial |
| Calibri | Calibri Light |
| Cambria | Calibri |
| Trebuchet MS | Calibri |
| Impact | Arial |
| Palatino | Garamond |
| Consolas | Calibri |

**Choose an interesting font pairing** — don't default to Arial for everything. Pick a header font with personality and pair it with a clean body font.

### No Bold for Body Text

**Plain body text and caption/legend text must NOT use bold.**

- Body paragraphs, descriptions → normal weight
- Captions, legends, footnotes → normal weight
- Reserve bold for titles and headings only

```javascript
// Correct
slide.addText("Main Title", { bold: true, fontSize: 36, fontFace: "Arial" });
slide.addText("Body text here.", { bold: false, fontSize: 14, fontFace: "Arial" });

// Wrong
slide.addText("Body text here.", { bold: true, fontSize: 14 });
```

---

## Chinese Localization (中文本地化)

When generating Chinese content, apply these adaptations:

| Dimension | English Default | Chinese Adaptation |
|-----------|----------------|-------------------|
| **Font** | Arial, Georgia | Microsoft YaHei (微软雅黑), PingFang SC (苹方) |
| **Body font size** | 14-16pt | 16-18pt (Chinese glyphs need larger size) |
| **Line height** | 1.2x | 1.5-1.8x (more vertical space for readability) |
| **Chars per line** | unlimited | 15-20 Chinese characters max |
| **Alignment** | justify | left-align (especially for PPT) |
| **Spacing** | n/a | Half-width space between Chinese and English/numbers |

### Chinese Font Priority

```javascript
// For titles
fontFace: "Microsoft YaHei"  // Windows
fontFace: "PingFang SC"      // macOS

// For body (same family, lighter weight)
fontFace: "Microsoft YaHei"
```

### Mixed Chinese-English Text

Always insert a half-width space between Chinese characters and English/numbers:

```
✅ 本次会议有 12 位参与者，使用 Zoom 平台
❌ 本次会议有12位参与者，使用Zoom平台
```
