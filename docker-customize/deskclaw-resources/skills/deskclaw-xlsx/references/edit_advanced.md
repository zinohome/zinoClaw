## 5. High-Risk Operations — Cascade Effects

### 5.1 Inserting a Row in the Middle

Inserting a row at position N shifts all rows from N downward. Every reference to those rows in every XML file must be updated.

**Files to check and update:**

| XML region | What to update | Example shift |
|------------|---------------|---------------|
| Worksheet `<row r="...">` attributes | Increment row number for all rows >= N | `r="7"` → `r="8"` |
| All `<c r="...">` within those rows | Increment row number in cell address | `r="A7"` → `r="A8"` |
| All `<f>` formula text in any sheet | Shift absolute row references >= N | `B7` → `B8` |
| `<mergeCell ref="...">` | Shift start and end rows | `A7:C7` → `A8:C8` |
| `<conditionalFormatting sqref="...">` | Shift range | `A5:D20` → `A5:D21` |
| `<dataValidations sqref="...">` | Shift range | `B6:B50` → `B7:B51` |
| `xl/charts/chartN.xml` data source ranges | Shift series ranges | `Sheet1!$B$5:$B$20` → `Sheet1!$B$6:$B$21` |
| `xl/pivotTables/*.xml` source ranges | Shift source data range | Handle with extreme care — see Section 7 |
| `<dimension ref="...">` | Expand to include new extent | `A1:D20` → `A1:D21` |
| `xl/tables/tableN.xml` `ref` attribute | Expand table boundary | `A1:D20` → `A1:D21` |

**Do not attempt row insertion manually in large or formula-heavy files.** Use the dedicated shift script instead:

```bash
# Insert 1 row at row 5: all rows 5 and below shift down by 1
python3 SKILL_DIR/scripts/xlsx_shift_rows.py /tmp/xlsx_work/ insert 5 1

# Delete 1 row at row 8: all rows 9 and above shift up by 1
python3 SKILL_DIR/scripts/xlsx_shift_rows.py /tmp/xlsx_work/ delete 8 1
```

The script updates in one pass: `<row r="...">` attributes, `<c r="...">` cell addresses, all `<f>` formula text across every worksheet, `<mergeCell>` ranges, `<conditionalFormatting sqref="...">`, `<dataValidation sqref="...">`, `<dimension ref="...">`, table `ref` attributes in `xl/tables/`, chart series ranges in `xl/charts/`, and pivot cache source ranges in `xl/pivotCaches/`.

**After running the shift script, always repack and validate:**
```bash
python3 SKILL_DIR/scripts/xlsx_pack.py /tmp/xlsx_work/ output.xlsx
python3 SKILL_DIR/scripts/formula_check.py output.xlsx
```

**What the script does NOT update (review manually):**
- Named ranges in `xl/workbook.xml` `<definedNames>` — check and update if they reference shifted rows.
- Structured table references (`Table[@Column]`) inside formulas.
- External workbook links in `xl/externalLinks/`.

### 5.2 Inserting a Column in the Middle

Same cascade logic as row insertion, but for columns. Column references in formulas (`B`, `$C`, etc.) and in merged cell ranges, conditional formatting ranges, and chart data sources all need updating.

Column letter shifting is harder to automate safely. Prefer **appending columns at the end** whenever possible.

### 5.3 Deleting a Row or Column

Deletion is more dangerous than insertion because any formula that referenced a deleted row or column will become `#REF!`. Before deleting:

1. Search all `<f>` elements for references to the deleted range.
2. If any formula references a cell in the deleted row/column, do not delete — instead, either clear the row's data or consult the user.
3. After deletion, shift all references to rows/columns beyond the deletion point downward/leftward.

---

