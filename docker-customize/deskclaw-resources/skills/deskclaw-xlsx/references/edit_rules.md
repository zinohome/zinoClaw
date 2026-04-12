## 6. Template Filling — Identifying and Populating Input Cells

Templates designate certain cells as input zones. Common patterns to recognize them:

### 6.1 How Templates Signal Input Zones

| Signal | XML manifestation | What to look for |
|--------|-------------------|-----------------|
| Blue font color | `s` attribute pointing to a `cellXfs` entry with `fontId` → `<color rgb="000000FF"/>` | Check `styles.xml` to decode `s` values |
| Yellow fill (highlight) | `s` → `fillId` → `<fill><patternFill><fgColor rgb="00FFFF00"/>` | |
| Empty `<v>` element | `<c r="B5"><v></v></c>` or cell entirely absent from `<row>` | The cell has no value yet |
| Comment/annotation near cell | `xl/comments1.xml` with `ref="B5"` | Comments often label input fields |
| Named ranges | `xl/workbook.xml` `<definedName>` elements | Template may define `InputRevenue` etc. |

### 6.2 Filling a Template Cell

Do not change `s` attributes. Do not change `t` attributes unless you must change from empty to typed. Only change `<v>` or add `<f>`.

**Before (empty input cell with style preserved):**
```xml
<c r="C5" s="3">
  <v></v>
</c>
```

**After (filled with a number, style unchanged):**
```xml
<c r="C5" s="3">
  <v>125000</v>
</c>
```

**After (filled with text — requires shared string entry first):**
```xml
<!-- 1. Append to sharedStrings.xml: <si><t>North Region</t></si> at index 7 -->
<c r="C5" t="s" s="3">
  <v>7</v>
</c>
```

**After (filled with a formula, preserving style):**
```xml
<c r="C5" s="3">
  <f>Assumptions!D12</f>
  <v></v>
</c>
```

### 6.3 Locating Input Zones Without Opening the File in Excel

After unpacking, decode the style index on suspected input cells to determine if they have the template's input color:

1. Note the `s` value on the cell (e.g., `s="4"`).
2. In `xl/styles.xml`, find `<cellXfs>` and look at the 5th entry (index 4).
3. Note its `fontId` (e.g., `fontId="2"`).
4. In `<fonts>`, look at the 3rd entry (index 2) and check for `<color rgb="000000FF"/>` (blue) or other input marker.

If the template uses named ranges as input fields, read them from `xl/workbook.xml`:
```xml
<definedNames>
  <definedName name="InputGrowthRate">Assumptions!$B$5</definedName>
  <definedName name="InputDiscountRate">Assumptions!$B$6</definedName>
</definedNames>
```

Fill the target cells (`Assumptions!B5`, `Assumptions!B6`) directly.

### 6.4 Template Filling Rules

- Fill only cells the template designated as inputs. Do not fill cells that are formula-driven.
- Do not apply new styles when filling. The template's formatting is the deliverable.
- Do not add or remove rows inside the template's data area unless the template explicitly has an "append here" zone.
- After filling, verify that no formula errors were introduced: some templates have input-validation formulas that produce `#VALUE!` if the wrong data type is entered.

---

## 7. Files You Must Never Modify

### 7.1 Absolute no-touch list

| File / location | Why |
|-----------------|-----|
| `xl/vbaProject.bin` | Binary VBA bytecode. Any byte modification corrupts the macro project. Editing even one bit makes the macros fail to load. |
| `xl/pivotCaches/pivotCacheDefinition*.xml` | The cache definition ties the pivot table to its source data. Editing it without also updating the corresponding `pivotTable*.xml` will corrupt the pivot. |
| `xl/pivotTables/*.xml` | Pivot table XML is tightly coupled with the cache definition and with internal state Excel rebuilds on load. Do not edit. If you shifted rows and the pivot's source range now points to wrong data, update only the `<cacheSource>` range in the cache definition, and only the `ref` attribute in the pivot table — no other changes. |
| `xl/slicers/*.xml` | Slicers are connected to specific cache IDs and pivot fields. Breaking these connections silently corrupts the file. |
| `xl/connections.xml` | External data connections. Editing breaks live data refresh. |
| `xl/externalLinks/` | External workbook links. The binary `.bin` files in here must not be modified. |

### 7.2 Conditionally safe files (update only specific attributes)

| File | What you may update | What to leave alone |
|------|--------------------|--------------------|
| `xl/charts/chartN.xml` | Data series range references (`<numRef><f>`) after a row/column shift | Chart type, formatting, layout |
| `xl/tables/tableN.xml` | `ref` attribute on `<table>` after adding rows | Column definitions, style info |
| `xl/pivotCaches/pivotCacheDefinition*.xml` | `ref` attribute on `<cacheSource><worksheetSource>` after shifting source data | All other content |

---

## 8. Validation After Every Edit

Never skip validation. Even a one-character change in a formula can cause cascading errors.

```bash
# Pack
python3 SKILL_DIR/scripts/xlsx_pack.py /tmp/xlsx_work/ output.xlsx

# Static formula validation (always run)
python3 SKILL_DIR/scripts/formula_check.py output.xlsx

# Dynamic validation (if LibreOffice available)
python3 SKILL_DIR/scripts/libreoffice_recalc.py output.xlsx /tmp/recalc.xlsx
python3 SKILL_DIR/scripts/formula_check.py /tmp/recalc.xlsx
```

If `formula_check.py` reports any error:
1. Unpack the output file again (it is the packed version).
2. Locate the reported cell in the worksheet XML.
3. Fix the `<f>` element.
4. Repack and re-validate.

Do not deliver the file until `formula_check.py` reports zero errors.

---

## 9. Absolute Rules Summary

| Rule | Rationale |
|------|-----------|
| Never use openpyxl `load_workbook` + `save` on an existing file | Round-trip destroys pivot tables, VBA, sparklines, slicers |
| Never delete or reorder existing `<si>` entries in sharedStrings | Breaks every cell referencing that index |
| Never delete or reorder existing `<xf>` entries in `<cellXfs>` | Breaks every cell using that style index |
| Never modify `vbaProject.bin` | Binary file; any change corrupts VBA |
| Never change `sheetId` when renaming a sheet | Internal ID is stable; changing it breaks relationships |
| Never skip post-edit validation | Leaves broken references undetected |
| Never edit more XML nodes than required | Extra changes risk introducing subtle corruption |
| Clear `<v>` to empty string when changing a formula | Prevents stale cached value from misleading downstream consumers |
| Append-only to sharedStrings | Existing indexes must remain valid |
| Append-only to styles collections | Existing style indexes must remain valid |
