## Font Selection

### Recommended CJK Fonts

| Language | Serif (正文) | Sans (标题) | Notes |
|----------|-------------|-------------|-------|
| **Simplified Chinese** | 宋体 (SimSun) | 微软雅黑 (Microsoft YaHei) | YaHei for screen, SimSun for print |
| **Simplified Chinese** | 仿宋 (FangSong) | 黑体 (SimHei) | Government documents |
| **Traditional Chinese** | 新細明體 (PMingLiU) | 微軟正黑體 (Microsoft JhengHei) | Taiwan standard |
| **Japanese** | MS 明朝 (MS Mincho) | MS ゴシック (MS Gothic) | Classic pairing |
| **Japanese** | 游明朝 (Yu Mincho) | 游ゴシック (Yu Gothic) | Modern, Windows 10+ |
| **Korean** | 바탕 (Batang) | 맑은 고딕 (Malgun Gothic) | Standard pairing |

### Government Document Fonts (公文)

| Element | Font | Size |
|---------|------|------|
| 标题 (title) | 小标宋 (FZXiaoBiaoSong-B05S) | 二号 (22pt) |
| 一级标题 | 黑体 (SimHei) | 三号 (16pt) |
| 二级标题 | 楷体_GB2312 (KaiTi_GB2312) | 三号 (16pt) |
| 三级标题 | 仿宋_GB2312 加粗 | 三号 (16pt) |
| 正文 (body) | 仿宋_GB2312 (FangSong_GB2312) | 三号 (16pt) |
| 附注/页码 | 宋体 (SimSun) | 四号 (14pt) |

---


## Font Size Names

CJK uses named sizes. Map to points and `w:sz` half-point values:

| 字号 | Points | `w:sz` | Common Use |
|------|--------|--------|------------|
| 初号 | 42pt | 84 | Display title |
| 小初 | 36pt | 72 | Large title |
| 一号 | 26pt | 52 | Chapter heading |
| 小一 | 24pt | 48 | Major heading |
| 二号 | 22pt | 44 | Document title (公文) |
| 小二 | 18pt | 36 | Western H1 equivalent |
| 三号 | 16pt | 32 | CJK heading / 公文 body |
| 小三 | 15pt | 30 | Sub-heading |
| 四号 | 14pt | 28 | CJK subheading |
| 小四 | 12pt | 24 | Standard body (CJK) |
| 五号 | 10.5pt | 21 | Compact CJK body |
| 小五 | 9pt | 18 | Footnotes |
| 六号 | 7.5pt | 15 | Fine print |

---


## RunFonts Mapping

OpenXML uses four font slots to handle multilingual text:

```xml
<w:rFonts
  w:ascii="Calibri"        <!-- Latin characters (U+0000–U+007F) -->
  w:hAnsi="Calibri"        <!-- Latin extended, Greek, Cyrillic -->
  w:eastAsia="SimSun"      <!-- CJK Unified Ideographs, Kana, Hangul -->
  w:cs="Arial"             <!-- Arabic, Hebrew, Thai, Devanagari -->
/>
```

**Word's character classification logic:**

1. Character is in CJK range → uses `w:eastAsia` font
2. Character is in complex script range → uses `w:cs` font
3. Character is basic Latin (ASCII) → uses `w:ascii` font
4. Everything else → uses `w:hAnsi` font

**Key**: `w:eastAsia` is the **only** way to set CJK fonts. Setting just `w:ascii` will NOT affect CJK characters. Mixed text within a single run auto-switches fonts at the character level — no need for separate runs.

### Document Defaults

```xml
<w:docDefaults>
  <w:rPrDefault>
    <w:rPr>
      <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="SimSun" w:cs="Arial" />
      <w:sz w:val="22" />
      <w:szCs w:val="22" />
      <w:lang w:val="en-US" w:eastAsia="zh-CN" />
    </w:rPr>
  </w:rPrDefault>
</w:docDefaults>
```

`w:lang w:eastAsia` helps Word resolve ambiguous characters (e.g., punctuation shared between CJK and Latin).

---

