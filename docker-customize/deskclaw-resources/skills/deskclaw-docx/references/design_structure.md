## 4. Alignment & Grid

### Why It Works

Alignment creates invisible lines that the eye follows down the page. When
elements share the same left edge, the reader perceives order and intention.
When elements are slightly misaligned (off by a few twips), the page looks
sloppy even if the reader cannot consciously identify why.

**Left-align vs Justify:**

- **Left-aligned** (ragged right) is best for English and other Latin-script
  languages. The uneven right edge actually helps reading because each line
  has a unique silhouette, making it easier for the eye to find the next line.
  Justified text forces uneven word spacing that creates distracting "rivers"
  of white running vertically through paragraphs.

- **Justified** is best for CJK text. Chinese, Japanese, and Korean characters
  are monospaced by design -- each occupies the same cell in an invisible grid.
  Justification preserves this grid perfectly. Ragged right in CJK text breaks
  the grid and looks untidy.

**Indentation rule:** Use first-line indent OR paragraph spacing to separate
paragraphs -- never both. They serve the same purpose (marking paragraph
boundaries). Using both wastes space and creates visual stutter.

- Western convention: paragraph spacing (no indent) is more modern.
- CJK convention: first-line indent of 2 characters is standard.
- Academic convention: first-line indent of 0.5 inch is traditional.

### Good Example

```xml
<!-- English body: left-aligned, paragraph spacing, no indent -->
<w:pPr>
  <w:jc w:val="left"/>
  <w:spacing w:after="160" w:line="276" w:lineRule="auto"/>
  <!-- No w:ind firstLine -->
</w:pPr>

<!-- CJK body: justified, first-line indent 2 chars, no paragraph spacing -->
<w:pPr>
  <w:jc w:val="both"/>
  <w:spacing w:after="0" w:line="360" w:lineRule="auto"/>
  <w:ind w:firstLineChars="200"/>
</w:pPr>

<!-- Tab stops creating aligned columns -->
<w:pPr>
  <w:tabs>
    <w:tab w:val="left" w:pos="2880"/>   <!-- 2 inches -->
    <w:tab w:val="right" w:pos="9360"/>  <!-- 6.5 inches (right margin) -->
  </w:tabs>
</w:pPr>
```

```
  English paragraph separation (good -- spacing, no indent):

  This is the first paragraph with some text
  that wraps to a second line naturally.

  This is the second paragraph. The gap above
  clearly marks the boundary.


  CJK paragraph separation (good -- indent, no spacing):

  　　第一段正文内容从这里开始，使用两个字符
  的首行缩进来标记段落边界。
  　　第二段紧跟其后，没有段间距，但首行缩进
  清晰地标识了新段落的开始。
```

### Bad Example

```xml
<!-- English body: justified (creates word-spacing rivers) -->
<w:pPr>
  <w:jc w:val="both"/>
  <w:spacing w:after="160" w:line="276" w:lineRule="auto"/>
  <w:ind w:firstLine="720"/>  <!-- BOTH indent AND spacing: redundant -->
</w:pPr>

<!-- CJK body: left-aligned (breaks character grid) -->
<w:pPr>
  <w:jc w:val="left"/>
  <w:spacing w:after="200" w:line="276" w:lineRule="auto"/>
  <!-- No indent, using spacing instead -- unidiomatic for CJK -->
</w:pPr>
```

Problems:
- Justified English text with narrow columns creates uneven word gaps.
- Using both first-line indent AND paragraph spacing is redundant.
- Left-aligned CJK breaks the character grid that CJK readers expect.
- CJK with spacing-based separation looks like translated western layout.

### Quick Test

1. **River test**: in justified English text, squint and look for vertical
   white streaks running through the paragraph. If you see them, switch to
   left-align or increase the column width.
2. **Double signal check**: does the document use BOTH first-line indent AND
   paragraph spacing? If yes, remove one. Choose indent for CJK/academic,
   spacing for modern western.
3. **Tab alignment**: if you use tabs for columns, do all tab stops across
   the document use the same positions? Inconsistent tab stops create jagged
   invisible grid lines.

---


## 5. Repetition & Consistency

### Why It Works

Consistency is a trust signal. When a reader sees that every H2 looks the same,
every table follows the same pattern, and every page number sits in the same
spot, they unconsciously trust that the document was crafted with care. A single
inconsistency -- one H2 that is 15pt instead of 14pt, one table with different
borders -- breaks that trust and makes the reader question the content.

Consistency also reduces cognitive load. Once the reader learns "bold dark blue
= section heading," they stop spending mental effort on identifying structure
and focus entirely on content. Every inconsistency forces them to re-evaluate:
"Is this a different kind of heading, or did someone just forget to apply the
style?"

The implementation rule is simple: **use named styles, not direct formatting.**
If you define Heading2 as a style and apply it everywhere, consistency is
automatic. If you manually set font size, bold, and color on each heading
individually, inconsistency is inevitable.

### Good Example

```xml
<!-- Define styles once in styles.xml -->
<w:style w:type="paragraph" w:styleId="Heading2">
  <w:name w:val="heading 2"/>
  <w:basedOn w:val="Normal"/>
  <w:next w:val="Normal"/>
  <w:pPr>
    <w:keepNext/>
    <w:keepLines/>
    <w:spacing w:before="360" w:after="120"/>
    <w:outlineLvl w:val="1"/>
  </w:pPr>
  <w:rPr>
    <w:rFonts w:asciiTheme="majorHAnsi" w:hAnsiTheme="majorHAnsi"/>
    <w:b/>
    <w:sz w:val="32"/>
    <w:color w:val="1F3864"/>
  </w:rPr>
</w:style>

<!-- Apply consistently: every H2 references the style -->
<w:p>
  <w:pPr>
    <w:pStyle w:val="Heading2"/>
    <!-- No direct formatting overrides -->
  </w:pPr>
  <w:r><w:t>Market Analysis</w:t></w:r>
</w:p>
```

When using a table style, define it once and reference it for every table:

```xml
<!-- All tables reference the same style -->
<w:tblPr>
  <w:tblStyle w:val="GridTable4Accent1"/>
  <w:tblW w:w="0" w:type="auto"/>
</w:tblPr>
```

### Bad Example

```xml
<!-- First H2: manually formatted -->
<w:p>
  <w:pPr>
    <w:spacing w:before="360" w:after="120"/>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:b/>
      <w:sz w:val="32"/>
      <w:color w:val="1F3864"/>
    </w:rPr>
    <w:t>Market Analysis</w:t>
  </w:r>
</w:p>

<!-- Second H2: slightly different (16pt instead of 16pt?  No, 15pt!) -->
<w:p>
  <w:pPr>
    <w:spacing w:before="240" w:after="160"/>  <!-- different spacing! -->
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:b/>
      <w:sz w:val="30"/>   <!-- 15pt instead of 16pt! -->
      <w:color w:val="2E74B5"/>  <!-- different shade of blue! -->
    </w:rPr>
    <w:t>Financial Overview</w:t>
  </w:r>
</w:p>
```

Problems:
- No style references -- everything is direct formatting.
- Second H2 has different size (30 vs 32), color, and spacing.
- If there are 20 headings, each could drift slightly differently.
- Changing the design later means editing every heading individually.

### Quick Test

1. **Style audit**: does every paragraph reference a `w:pStyle`? If you find
   paragraphs with only direct formatting and no style, that is a consistency
   risk.
2. **Search for variance**: search the XML for all `w:sz` values used with
   `w:b` (bold). If you find three different sizes for what should be the same
   heading level, there is an inconsistency.
3. **Table check**: do all tables in the document reference the same
   `w:tblStyle`? If some tables have manual border definitions while others
   use a style, the document will look patchy.
4. **Page numbers**: check that header/footer content is defined in the
   default section properties and inherited by all sections, not redefined
   inconsistently in each section.

---

