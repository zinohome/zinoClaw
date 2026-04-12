## 3. styles.xml Surgical Operations

### 3.1 Auditing Existing Styles: Understanding the cellXfs Indirect Reference Chain

A cell's `s` attribute points to a position index (0-based) in `cellXfs`, and each `<xf>` entry in `cellXfs` references its respective definition libraries through `fontId`, `fillId`, `borderId`, and `numFmtId`.

Reference chain diagram:

```
Cell <c s="6">
    | Look up cellXfs by 0-based index
cellXfs[6] -> numFmtId="164" fontId="2" fillId="0" borderId="0"
    |            |               |          |
numFmts         fonts[2]      fills[0]   borders[0]
id=164          color=00000000  (no fill)  (no border)
$#,##0...       black
```

Audit steps:

**Step 1**: Read `<numFmts>` and record all declared custom formats and their IDs:
```xml
<numFmts count="4">
  <numFmt numFmtId="164" formatCode="$#,##0;($#,##0);&quot;-&quot;"/>
  <numFmt numFmtId="165" formatCode="0.0%"/>
  <numFmt numFmtId="166" formatCode="0.0x"/>
  <numFmt numFmtId="167" formatCode="#,##0"/>
</numFmts>
```
Record: current maximum custom numFmtId = 167, next available ID = 168.

**Step 2**: Read `<fonts>` and list each `<font>` by 0-based index with its color and style:
```
fontId=0 -> No explicit color (theme default black)
fontId=1 -> color rgb="000000FF" (blue, input role)
fontId=2 -> color rgb="00000000" (black, formula role)
fontId=3 -> color rgb="00008000" (green, cross-sheet reference role)
fontId=4 -> <b/> + color rgb="00000000" (bold black, header)
```

**Step 3**: Read `<fills>` and confirm that fills[0] and fills[1] are spec-mandated reserved entries (never delete):
```
fillId=0 -> patternType="none" (spec-mandated)
fillId=1 -> patternType="gray125" (spec-mandated)
fillId=2 -> Yellow highlight (if present)
```

**Step 4**: Read `<cellXfs>` and list each `<xf>` entry by 0-based index with its combination:
```
index 0 -> numFmtId=0,   fontId=0, fillId=0 -> Default style
index 1 -> numFmtId=0,   fontId=1, fillId=0 -> Blue font general (input)
index 5 -> numFmtId=164, fontId=1, fillId=0 -> Blue font currency (currency input)
index 6 -> numFmtId=164, fontId=2, fillId=0 -> Black font currency (currency formula)
...
```

**Step 5**: Verify that all count attributes match the actual number of elements (count mismatches will cause Excel to refuse to open the file).

### 3.2 Safely Appending New Styles (Golden Rule: Append Only, Never Modify Existing xf)

**Never modify existing `<xf>` entries**. Modifications will affect all cells that already reference that index, breaking existing formatting. Only append new entries at the end.

Complete atomic operation sequence for appending new styles (all 5 steps must be executed):

**Step 1**: Determine if a new `<numFmt>` is needed

Built-in formats (ID 0–163) skip this step. Custom formats are appended to the end of `<numFmts>`:
```xml
<numFmts count="5">  <!-- count +1 -->
  <!-- Keep existing entries unchanged -->
  <numFmt numFmtId="164" formatCode="$#,##0;($#,##0);&quot;-&quot;"/>
  <numFmt numFmtId="165" formatCode="0.0%"/>
  <numFmt numFmtId="166" formatCode="0.0x"/>
  <numFmt numFmtId="167" formatCode="#,##0"/>
  <!-- Newly appended -->
  <numFmt numFmtId="168" formatCode="$#,##0.00;($#,##0.00);&quot;-&quot;"/>
</numFmts>
```

**Step 2**: Determine if a new `<font>` is needed

Check whether the existing fonts already contain a matching color+style combination. If not, append to the end of `<fonts>`:
```xml
<fonts count="6">  <!-- count +1 -->
  <!-- Keep existing entries unchanged -->
  ...
  <!-- Newly appended: red font (external link role), new fontId = 5 -->
  <font>
    <sz val="11"/>
    <name val="Calibri"/>
    <color rgb="00FF0000"/>
  </font>
</fonts>
```
New fontId = the count value before appending (when original count=5, new fontId=5).

**Step 3**: Determine if a new `<fill>` is needed

If a new background color is needed, append to the end of `<fills>` (note: fills[0] and fills[1] must never be modified):
```xml
<fills count="4">  <!-- count +1 -->
  <fill><patternFill patternType="none"/></fill>       <!-- 0: spec-mandated -->
  <fill><patternFill patternType="gray125"/></fill>    <!-- 1: spec-mandated -->
  <fill>                                               <!-- 2: yellow highlight -->
    <patternFill patternType="solid">
      <fgColor rgb="00FFFF00"/>
      <bgColor indexed="64"/>
    </patternFill>
  </fill>
  <!-- Newly appended: light gray fill (projection period distinction), new fillId = 3 -->
  <fill>
    <patternFill patternType="solid">
      <fgColor rgb="00D3D3D3"/>
      <bgColor indexed="64"/>
    </patternFill>
  </fill>
</fills>
```

**Step 4**: Append a new `<xf>` combination at the end of `<cellXfs>`
```xml
<cellXfs count="14">  <!-- count +1 -->
  <!-- Keep existing entries 0-12 unchanged -->
  ...
  <!-- Newly appended index=13: currency with cents formula (black font + numFmtId=168) -->
  <xf numFmtId="168" fontId="2" fillId="0" borderId="0" xfId="0"
      applyFont="1" applyNumberFormat="1"/>
</cellXfs>
```
New style index = the count value before appending (when original count=13, new index=13).

**Step 5**: Record the new style index; subsequently set the `s` attribute of corresponding cells in the sheet XML to this value.

### 3.3 AARRGGBB Color Format Explanation

OOXML's `rgb` attribute uses **8-digit hexadecimal AARRGGBB** format (not HTML's 6-digit RRGGBB):

```
AA  RR  GG  BB
|   |   |   |
Alpha Red Green Blue
```

- Alpha channel: `00` = fully opaque (normal use value); `FF` = fully transparent (invisible, never use this)
- Financial color standards always use `00` as the Alpha prefix

| Color | AARRGGBB | Corresponding Role |
|-------|----------|-------------------|
| Blue (input) | `000000FF` | Hard-coded assumptions |
| Black (formula) | `00000000` | Calculated results |
| Green (cross-sheet reference) | `00008000` | Same-workbook cross-sheet |
| Red (external link) | `00FF0000` | References to other files |
| Yellow (review-required fill) | `00FFFF00` | Key assumption highlight |
| Light gray (projection period fill) | `00D3D3D3` | Distinguishing historical vs. forecast periods |
| White | `00FFFFFF` | Pure white fill |

**Common mistake**: Mistakenly writing HTML format `#0000FF` as `FF0000FF` (Alpha=FF makes the color fully transparent and invisible). Correct format: `000000FF`.

### 3.4 numFmtId Assignment Rules

```
ID 0-163    -> Excel/LibreOffice built-in formats, no declaration needed in <numFmts>, reference directly in <xf>
ID 164+     -> Custom formats, must be explicitly declared as <numFmt> elements in <numFmts>
```

Rules for assigning new IDs:
1. Read all `numFmtId` attribute values in the current `<numFmts>`
2. Take the maximum value + 1 as the next custom format ID
3. Do not reuse existing IDs; do not skip numbers

The minimal_xlsx template pre-defines IDs: 164, 165, 166, 167. The next available ID is 168.

---

## 4. Pre-defined Style Index Complete Reference Table (13 Slots)

The following are the 13 style slots (cellXfs index 0–12) pre-defined in the minimal_xlsx template's `styles.xml`, which can be directly referenced in the cell `s` attribute in sheet XML:

| Index | Semantic Role | Font Color | Fill | numFmtId | Format Display | Typical Use |
|-------|--------------|------------|------|----------|---------------|-------------|
| **0** | Default style | Theme black | None | 0 | General | Cells requiring no special formatting |
| **1** | Input / assumption (general) | Blue `000000FF` | None | 0 | General | Text-type assumptions, flags |
| **2** | Formula / calculated result (general) | Black `00000000` | None | 0 | General | Text concatenation formulas, non-numeric calculations |
| **3** | Cross-sheet reference (general) | Green `00008000` | None | 0 | General | Values pulled from cross-sheet (general format) |
| **4** | Header (bold) | Bold black | None | 0 | General | Row/column headings |
| **5** | Currency input | Blue `000000FF` | None | 164 | $1,234 / ($1,234) / - | Amount inputs in the assumptions area |
| **6** | Currency formula | Black `00000000` | None | 164 | $1,234 / ($1,234) / - | Amount calculations in the model area (revenue, EBITDA) |
| **7** | Percentage input | Blue `000000FF` | None | 165 | 12.5% | Rate inputs in the assumptions area (growth rate, gross margin assumptions) |
| **8** | Percentage formula | Black `00000000` | None | 165 | 12.5% | Rate calculations in the model area (actual gross margin) |
| **9** | Integer (comma) input | Blue `000000FF` | None | 167 | 12,345 | Quantity inputs in the assumptions area (employee count) |
| **10** | Integer (comma) formula | Black `00000000` | None | 167 | 12,345 | Quantity calculations in the model area |
| **11** | Year input | Blue `000000FF` | None | 1 | 2024 | Column header years (no thousands separator) |
| **12** | Key assumption highlight | Blue `000000FF` | Yellow `00FFFF00` | 0 | General | Key parameters pending review or confirmation |

**Selection guide**:
- Determine "input" vs. "formula" -> Choose odd-numbered (input/blue) or even-numbered (formula/black) paired slots
- Determine data type -> Choose the corresponding currency (5/6) / percentage (7/8) / integer (9/10) / year (11) slot
- Cross-sheet reference needing number format -> Append a new green + number format combination (see Section 5.4)
- Parameter pending review -> index 12

---

