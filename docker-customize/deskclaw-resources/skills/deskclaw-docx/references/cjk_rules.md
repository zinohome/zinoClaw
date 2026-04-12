## Punctuation & Line Breaking

### Full-Width vs Half-Width

CJK text uses full-width punctuation:

| Type | CJK | Latin |
|------|-----|-------|
| Period | 。(U+3002) | . |
| Comma | ，(U+FF0C) 、(U+3001) | , |
| Colon | ：(U+FF1A) | : |
| Semicolon | ；(U+FF1B) | ; |
| Quotes | 「」『』 or ""'' | "" '' |
| Parentheses | （）(U+FF08/09) | () |

In mixed text, use the punctuation style of the **surrounding language context**.

### OpenXML Controls

```xml
<w:pPr>
  <w:adjustRightInd w:val="true" />   <!-- Adjust right indent for CJK punctuation -->
  <w:snapToGrid w:val="true" />        <!-- Align to document grid -->
  <w:kinsoku w:val="true" />           <!-- Enable CJK line breaking rules -->
  <w:overflowPunct w:val="true" />     <!-- Allow punctuation to overflow margins -->
</w:pPr>
```

### Kinsoku Rules (禁則処理)

Prevents certain characters from appearing at the start or end of a line:
- **Cannot start a line**: `）」』】〉》。、，！？；：` and closing brackets
- **Cannot end a line**: `（「『【〈《` and opening brackets

Word applies these automatically when `w:kinsoku` is enabled.

### Line Breaking

- CJK characters can break between **any two characters** (no word boundaries needed)
- Latin words within CJK text still follow word-boundary breaking
- `w:wordWrap w:val="false"` enables CJK-style breaking (break anywhere)

---


## Paragraph Indentation

### Chinese Standard: 2-Character Indent

Chinese body text conventionally uses a 2-character first-line indent:

```xml
<w:ind w:firstLineChars="200" />  <!-- 200 = 2 characters × 100 -->
```

Preferred over `w:firstLine` with fixed DXA because `firstLineChars` scales with font size.

| Indent | Value |
|--------|-------|
| 1 character | `w:firstLineChars="100"` |
| 2 characters | `w:firstLineChars="200"` |
| 3 characters | `w:firstLineChars="300"` |

---


## Line Spacing

- CJK characters are taller than Latin characters at the same point size
- Default `1.0` line spacing may feel cramped with CJK text
- Recommended: `1.15–1.5` for mixed CJK+Latin, `1.0` with fixed 28pt for 公文

### Auto Spacing

```xml
<w:pPr>
  <w:autoSpaceDE w:val="true"/>  <!-- auto space between CJK and Latin -->
  <w:autoSpaceDN w:val="true"/>  <!-- auto space between CJK and numbers -->
</w:pPr>
```

Adds ~¼ em spacing between CJK and non-CJK characters automatically. **Recommended: always enable.**

---


## GB/T 9704

Chinese government document standard (党政机关公文格式). These are **strict requirements**, not suggestions.

### Page Setup

| Parameter | Value | OpenXML |
|-----------|-------|---------|
| Page size | A4 (210×297mm) | Width=11906, Height=16838 |
| Top margin | 37mm | 2098 DXA |
| Bottom margin | 35mm | 1984 DXA |
| Left margin | 28mm | 1588 DXA |
| Right margin | 26mm | 1474 DXA |
| Characters/line | 28 | |
| Lines/page | 22 | |
| Line spacing | Fixed 28pt | `line="560"` lineRule="exact" |

### Document Structure

```
┌─────────────────────────────────┐
│     发文机关标志 (红头)           │  ← 小标宋 or 红色大字
│     ══════════════════ (红线)    │  ← Red #FF0000, 2pt
├─────────────────────────────────┤
│  发文字号: X机发〔2025〕X号      │  ← 仿宋 三号, centered
│                                 │
│  标题 (Title)                   │  ← 小标宋 二号, centered
│                                 │     可分多行，回行居中
│  主送机关:                      │  ← 仿宋 三号
│                                 │
│  正文 (Body)...                 │  ← 仿宋_GB2312 三号
│  一、一级标题                    │  ← 黑体 三号
│  （一）二级标题                  │  ← 楷体 三号
│  1. 三级标题                    │  ← 仿宋 三号 加粗
│  (1) 四级标题                   │  ← 仿宋 三号
│                                 │
│  附件: 1. xxx                   │  ← 仿宋 三号
│                                 │
│  发文机关署名                    │  ← 仿宋 三号
│  成文日期                       │  ← 仿宋 三号, 小写中文数字
├─────────────────────────────────┤
│  ══════════════════ (版记线)     │
│  抄送: xxx                      │  ← 仿宋 四号
│  印发机关及日期                   │  ← 仿宋 四号
└─────────────────────────────────┘
```

### Numbering System

```
一、        ← 黑体 (SimHei), no indentation
（一）      ← 楷体 (KaiTi), indented 2 chars
1.          ← 仿宋加粗 (FangSong Bold), indented 2 chars
(1)         ← 仿宋 (FangSong), indented 2 chars
```

### Colors

| Element | Color | Requirement |
|---------|-------|-------------|
| All body text | Black #000000 | Mandatory |
| 红头 (agency name) | Red #FF0000 | Mandatory |
| 红线 (separator) | Red #FF0000 | Mandatory |
| 公章 (official seal) | Red | Mandatory |

### Page Numbers

- Position: bottom center
- Format: `-X-` (dash-number-dash)
- Font: 宋体 四号 (SimSun 14pt, `sz="28"`)
- No page number on cover page if present

---


## Mixed Script

### Font Size Harmony

CJK characters appear larger than Latin characters at the same point size. Compensation:

- If body is Calibri 11pt, pair with CJK at 11pt (same size — CJK looks slightly larger but acceptable)
- If precise visual match needed, CJK can be set 0.5–1pt smaller
- In practice, same point size is standard — don't over-optimize

### Bold and Italic

- **Chinese/Japanese have no true italic.** Word synthesizes a slant which looks poor
- Use **bold** for emphasis in CJK text
- Use 着重号 (emphasis dots) for traditional emphasis: `<w:em w:val="dot"/>` on RunProperties

---

