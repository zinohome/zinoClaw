## 4. Precise XML Patterns for Common Edits

### 4.1 Changing a Numeric Cell Value

Find the `<c r="B5">` element in the worksheet XML and replace the `<v>` text.

**Before:**
```xml
<c r="B5">
  <v>1000</v>
</c>
```

**After (new value 1500):**
```xml
<c r="B5">
  <v>1500</v>
</c>
```

Rules:
- Do not add or remove the `s` attribute (style) unless explicitly changing the style.
- Do not add a `t` attribute — numbers omit `t` or use `t="n"`.
- Do not change the `r` attribute (cell reference).

---

### 4.2 Changing a Text Cell Value

Text cells reference the shared strings table by index (`t="s"`). You cannot edit the string in-place without affecting every other cell that uses the same index. The safe approach is to append a new entry.

**Before — shared strings file (`xl/sharedStrings.xml`):**
```xml
<sst count="4" uniqueCount="4">
  <si><t>Revenue</t></si>
  <si><t>Cost</t></si>
  <si><t>Margin</t></si>
  <si><t>Old Label</t></si>
</sst>
```

**After — append new string, increment counts:**
```xml
<sst count="5" uniqueCount="5">
  <si><t>Revenue</t></si>
  <si><t>Cost</t></si>
  <si><t>Margin</t></si>
  <si><t>Old Label</t></si>
  <si><t>New Label</t></si>
</sst>
```

New string is at index 4 (zero-based).

**Before — cell in worksheet XML:**
```xml
<c r="A7" t="s">
  <v>3</v>
</c>
```

**After — point to new index:**
```xml
<c r="A7" t="s">
  <v>4</v>
</c>
```

Rules:
- Never modify or delete existing `<si>` entries. Only append.
- Both `count` and `uniqueCount` must be incremented together.
- If the new string contains `&`, `<`, or `>`, escape them: `&amp;`, `&lt;`, `&gt;`.
- If the string has leading or trailing spaces, add `xml:space="preserve"` to `<t>`:
  ```xml
  <si><t xml:space="preserve">  indented text  </t></si>
  ```

---

### 4.3 Changing a Formula

Formulas are stored in `<f>` elements **without a leading `=`** (unlike what you type in Excel's UI).

**Before:**
```xml
<c r="C10">
  <f>SUM(C2:C9)</f>
  <v>4800</v>
</c>
```

**After (extended range):**
```xml
<c r="C10">
  <f>SUM(C2:C11)</f>
  <v></v>
</c>
```

Rules:
- Clear `<v>` to an empty string when changing the formula. The cached value is now stale.
- Do not add `t="s"` or any type attribute to formula cells. The `t` attribute is absent or uses a result-type value, not a formula marker.
- Cross-sheet references use `SheetName!CellRef`. If the sheet name contains spaces, wrap in single quotes: `'Q1 Data'!B5`.
- The `<f>` text must not include the leading `=`.

**Before (converting a hardcoded value to a live formula):**
```xml
<c r="D15">
  <v>95000</v>
</c>
```

**After:**
```xml
<c r="D15">
  <f>SUM(D2:D14)</f>
  <v></v>
</c>
```

---

### 4.4 Adding a New Data Row

Append after the last `<row>` element inside `<sheetData>`. Row numbers in OOXML are 1-based and must be sequential.

**Before (last row is row 10):**
```xml
  <row r="10">
    <c r="A10" t="s"><v>3</v></c>
    <c r="B10"><v>2023</v></c>
    <c r="C10"><v>88000</v></c>
    <c r="D10"><f>C10*1.1</f><v></v></c>
  </row>
</sheetData>
```

**After (new row 11 appended):**
```xml
  <row r="10">
    <c r="A10" t="s"><v>3</v></c>
    <c r="B10"><v>2023</v></c>
    <c r="C10"><v>88000</v></c>
    <c r="D10"><f>C10*1.1</f><v></v></c>
  </row>
  <row r="11">
    <c r="A11" t="s"><v>4</v></c>
    <c r="B11"><v>2024</v></c>
    <c r="C11"><v>96000</v></c>
    <c r="D11"><f>C11*1.1</f><v></v></c>
  </row>
</sheetData>
```

Rules:
- Every `<c>` inside the row must have `r` set to the correct cell address (e.g., `A11`).
- Text cells need `t="s"` and a sharedStrings index in `<v>`. Numeric cells omit `t`.
- Formula cells use `<f>` and an empty `<v>`.
- Copy the `s` attribute from the row above if you want matching styles. Do not invent a style index that does not exist in `styles.xml`.
- If the sheet contains a `<dimension>` element (e.g., `<dimension ref="A1:D10"/>`), update it to include the new row: `<dimension ref="A1:D11"/>`.
- If the sheet contains a `<tableparts>` referencing a table, update the table's `ref` attribute in the corresponding `xl/tables/tableN.xml` file.

---

### 4.5 Adding a New Column

Append new `<c>` elements to each existing `<row>` and, if present, update the `<cols>` section.

**Before (rows have columns A–C):**
```xml
<cols>
  <col min="1" max="3" width="14" customWidth="1"/>
</cols>
<sheetData>
  <row r="1">
    <c r="A1" t="s"><v>0</v></c>
    <c r="B1" t="s"><v>1</v></c>
    <c r="C1" t="s"><v>2</v></c>
  </row>
  <row r="2">
    <c r="A2"><v>100</v></c>
    <c r="B2"><v>200</v></c>
    <c r="C2"><v>300</v></c>
  </row>
</sheetData>
```

**After (adding column D):**
```xml
<cols>
  <col min="1" max="3" width="14" customWidth="1"/>
  <col min="4" max="4" width="14" customWidth="1"/>
</cols>
<sheetData>
  <row r="1">
    <c r="A1" t="s"><v>0</v></c>
    <c r="B1" t="s"><v>1</v></c>
    <c r="C1" t="s"><v>2</v></c>
    <c r="D1" t="s"><v>5</v></c>
  </row>
  <row r="2">
    <c r="A2"><v>100</v></c>
    <c r="B2"><v>200</v></c>
    <c r="C2"><v>300</v></c>
    <c r="D2"><f>A2+B2+C2</f><v></v></c>
  </row>
</sheetData>
```

Rules:
- Adding a column at the end (after the last existing column) is safe — no existing formula references shift.
- Inserting a column in the middle shifts all columns to the right, which requires the same cascade updates as row insertion (see Section 5).
- Update the `<dimension>` element if present.

---

### 4.6 Modifying or Adding Styles

Styles use a multi-level indirect reference chain. Read `ooxml-cheatsheet.md` for the full chain. The key rule: **only append new entries, never modify existing ones**.

**Scenario:** Add a blue-font style (for hardcoded input cells) that doesn't yet exist.

**Step 1 — Check if a matching font already exists in `xl/styles.xml`:**
```xml
<!-- Look inside <fonts> for an existing blue font -->
<font>
  <color rgb="000000FF"/>
  <!-- other attributes -->
</font>
```

If found, note its index (zero-based position in the `<fonts>` list). If not found, append.

**Step 2 — Append the new font if needed:**

Before:
```xml
<fonts count="3">
  <font>...</font>   <!-- index 0 -->
  <font>...</font>   <!-- index 1 -->
  <font>...</font>   <!-- index 2 -->
</fonts>
```

After:
```xml
<fonts count="4">
  <font>...</font>   <!-- index 0 -->
  <font>...</font>   <!-- index 1 -->
  <font>...</font>   <!-- index 2 -->
  <font>
    <b/>
    <sz val="11"/>
    <color rgb="000000FF"/>
    <name val="Calibri"/>
  </font>             <!-- index 3 (new) -->
</fonts>
```

**Step 3 — Append a new `<xf>` in `<cellXfs>`:**

Before:
```xml
<cellXfs count="5">
  <xf .../>   <!-- index 0 -->
  <xf .../>   <!-- index 1 -->
  <xf .../>   <!-- index 2 -->
  <xf .../>   <!-- index 3 -->
  <xf .../>   <!-- index 4 -->
</cellXfs>
```

After:
```xml
<cellXfs count="6">
  <xf .../>   <!-- index 0 -->
  <xf .../>   <!-- index 1 -->
  <xf .../>   <!-- index 2 -->
  <xf .../>   <!-- index 3 -->
  <xf .../>   <!-- index 4 -->
  <xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0"
      applyFont="1"/>   <!-- index 5 (new) -->
</cellXfs>
```

**Step 4 — Apply to target cells:**

Before:
```xml
<c r="B3">
  <v>0.08</v>
</c>
```

After:
```xml
<c r="B3" s="5">
  <v>0.08</v>
</c>
```

Rules:
- Never delete or reorder existing entries in `<fonts>`, `<fills>`, `<borders>`, `<cellXfs>`.
- Always update the `count` attribute when appending.
- The new `cellXfs` index = the old `count` value before appending (zero-based: if count was 5, new index is 5).
- Custom `numFmt` IDs must be 164 or above. IDs 0–163 are built-in and must not be re-declared.
- If the desired style already exists elsewhere in the file (on a similar cell), reuse its `s` index rather than creating a duplicate.

---

### 4.7 Renaming a Sheet

**Only `xl/workbook.xml` needs to change** — unless cross-sheet formulas reference the old name.

**Before (`xl/workbook.xml`):**
```xml
<sheet name="Sheet1" sheetId="1" r:id="rId1"/>
```

**After:**
```xml
<sheet name="Revenue" sheetId="1" r:id="rId1"/>
```

**If any formula in any worksheet references the old name, update those too:**

Before (`xl/worksheets/sheet2.xml`):
```xml
<c r="B5"><f>Sheet1!C10</f><v></v></c>
```

After:
```xml
<c r="B5"><f>Revenue!C10</f><v></v></c>
```

If the new name contains spaces:
```xml
<c r="B5"><f>'Q1 Revenue'!C10</f><v></v></c>
```

Scan all worksheet XML files for the old name:
```bash
grep -r "Sheet1!" /tmp/xlsx_work/xl/worksheets/
```

Rules:
- The `.rels` file and `[Content_Types].xml` do NOT need to change — they reference the XML file path, not the sheet name.
- `sheetId` must not change; it is a stable internal identifier.
- Sheet names are case-sensitive in formula references.

---

