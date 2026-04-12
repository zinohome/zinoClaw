# Common Aesthetic Recipes (5 Most Used)

## 1. Modern Corporate (现代企业)

Best for: Business reports, proposals, internal documents.

| Property | Value |
|----------|-------|
| Body font | Aptos / 微软雅黑 (EastAsia) |
| Body size | 11pt |
| Body color | #333333 |
| Heading 1 | Aptos Display 20pt, #1F3864, NOT bold |
| Heading 2 | Aptos Display 16pt, #1F3864, NOT bold |
| Heading 3 | Aptos 13pt, #1F3864, bold |
| Line spacing | 1.15x |
| Para spacing after | 8pt |
| Page size | US Letter (8.5" x 11") |
| Page margins | 1 inch all sides |
| H1 space before | 24pt |
| H2 space before | 18pt |
| Table style | Banded rows (#F2F2F2), horizontal borders only |

```python
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

doc = Document()

# Page setup
section = doc.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)
for attr in ('top_margin','bottom_margin','left_margin','right_margin'):
    setattr(section, attr, Inches(1))

# Body style
style = doc.styles['Normal']
style.font.name = 'Aptos'
style.font.size = Pt(11)
style.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
style.paragraph_format.space_after = Pt(8)
style.paragraph_format.line_spacing = 1.15
# CJK font
style.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

# Heading 1
h1 = doc.styles['Heading 1']
h1.font.name = 'Aptos Display'
h1.font.size = Pt(20)
h1.font.bold = False
h1.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
h1.paragraph_format.space_before = Pt(24)
h1.paragraph_format.space_after = Pt(6)
```

---

## 2. Academic Thesis (学术论文, APA-style)

Best for: Dissertations, research papers, academic reports.

| Property | Value |
|----------|-------|
| Body font | Times New Roman 12pt |
| Body color | #000000 |
| First-line indent | 0.5 inch |
| Heading 1 | 12pt bold, centered |
| Heading 2 | 12pt bold, left-aligned |
| Heading 3 | 12pt bold italic, left-aligned |
| Line spacing | 2.0x (double) |
| Para spacing after | 0pt (indent-separated) |
| Page size | US Letter |
| Page margins | Top/Bottom/Right 1in, Left 1.5in (binding) |
| Table style | Three-line (top 1.5pt, header 0.75pt, bottom 1.5pt) |

```python
style = doc.styles['Normal']
style.font.name = 'Times New Roman'
style.font.size = Pt(12)
style.paragraph_format.line_spacing = 2.0
style.paragraph_format.space_after = Pt(0)
style.paragraph_format.first_line_indent = Inches(0.5)

section = doc.sections[0]
section.left_margin = Inches(1.5)  # binding margin
```

---

## 3. Chinese Government (GB/T 9704 公文)

Best for: Government announcements, official communications.

| Property | Value |
|----------|-------|
| Body font | 仿宋 (FangSong) 16pt (三号) |
| Title font | 小标宋体 / SimSun 22pt (二号), centered |
| Heading 2 | 黑体 (SimHei) 16pt (三号) |
| Heading 3 | 楷体 (KaiTi) 16pt (三号) |
| Line spacing | Fixed 28pt exact |
| Para spacing | 0pt before and after |
| First-line indent | 2 characters (640 DXA) |
| Page size | A4 (210mm x 297mm) |
| Page margins | Top 37mm, Bottom 35mm, Left 28mm, Right 26mm |
| Page numbers | "-X-" format, 宋体 14pt (四号) |
| Chars per line | 28 |
| Lines per page | 22 |

```python
from docx.shared import Mm, Twips

section.page_width = Mm(210)
section.page_height = Mm(297)
section.top_margin = Mm(37)
section.bottom_margin = Mm(35)
section.left_margin = Mm(28)
section.right_margin = Mm(26)

style = doc.styles['Normal']
style.font.name = '仿宋'
style.element.rPr.rFonts.set(qn('w:eastAsia'), '仿宋')
style.font.size = Pt(16)
# Fixed 28pt line spacing
style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
style.paragraph_format.line_spacing = Pt(28)
# 2-char indent
style.paragraph_format.first_line_indent = Twips(640)
```

---

## 4. Minimal Modern (简约现代)

Best for: Design documents, creative briefs, tech company communications.

| Property | Value |
|----------|-------|
| Body font | Inter (fallback: Segoe UI) 10.5pt / 微软雅黑 |
| Body color | #444444 |
| Heading 1 | Inter 24pt, #111111, NOT bold |
| Heading 2 | Inter 16pt, #111111, NOT bold |
| Heading 3 | Inter 12pt, #111111, bold |
| Line spacing | 1.5x |
| Para spacing after | 12pt |
| Page margins | Top/Bottom 1in, Left/Right 1.5in |
| Accent color | #0066CC |
| Special | No page numbers |

---

## 5. IEEE Conference (IEEEtran)

Best for: IEEE conference submissions, transactions papers.

| Property | Value |
|----------|-------|
| Body font | Times New Roman 10pt |
| First-line indent | 0.125 inch |
| Title | 24pt, centered, NOT bold |
| Heading 1 | 10pt, small caps, centered |
| Heading 2 | 10pt, italic, left-aligned |
| Line spacing | 1.0x (single) |
| Para spacing | 0pt |
| Page size | US Letter |
| Page margins | Top 0.75in, Bottom 1in, Left/Right 0.625in |
| Columns | 2, gutter 0.25in |
| Captions | 8pt |
