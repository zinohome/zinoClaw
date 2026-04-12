# Minimal-Invasive Editing of Existing xlsx

Make precise, surgical changes to existing xlsx files while preserving everything you do not touch: styles, macros, pivot tables, charts, sparklines, named ranges, data validation, conditional formatting, and all other embedded content.

---

## 1. When to Use This Path

Use the edit (unpack → XML edit → pack) path whenever the task involves **modifying an existing xlsx file**:

- Template filling — populating designated input cells with values or formulas
- Data updates — replacing outdated numbers, text, or dates in a live file
- Content corrections — fixing wrong values, broken formulas, or mistyped labels
- Adding new data rows to an existing table
- Renaming a sheet
- Applying a new style to specific cells

Do NOT use this path for creating a brand-new workbook from scratch. For that, see `create.md`.

---

## 2. Why openpyxl round-trip Is Forbidden for Existing Files

openpyxl `load_workbook()` followed by `workbook.save()` is a **destructive operation** on any file that contains advanced features. The library silently drops content it does not understand:

| Feature | openpyxl behavior | Consequence |
|---------|-------------------|-------------|
| VBA macros (`vbaProject.bin`) | Dropped entirely | All automation is lost; file saved as `.xlsx` not `.xlsm` |
| Pivot tables (`xl/pivotTables/`) | Dropped | Interactive analysis is destroyed |
| Slicers | Dropped | Filter UI is lost |
| Sparklines (`<sparklineGroups>`) | Dropped | In-cell mini-charts disappear |
| Chart formatting details | Partially lost | Series colors, custom axes may revert |
| Print area / page breaks | Sometimes lost | Print layout changes |
| Custom XML parts | Dropped | Third-party data bindings broken |
| Theme-linked colors | May be de-themed | Colors converted to absolute, breaking theme switching |

Even on a "plain" file without these features, openpyxl may normalize whitespace in XML that Excel relies on, alter namespace declarations, or reset `calcMode` flags.

**The rule is absolute: never open an existing file with openpyxl for the purpose of re-saving it.**

The XML direct-edit approach is safe because it operates on the raw bytes. You only change the nodes you touch. Everything else is byte-equivalent to the original.

---

## 3. Standard Operating Procedure

### Step 1 — Unpack

```bash
python3 SKILL_DIR/scripts/xlsx_unpack.py input.xlsx /tmp/xlsx_work/
```

The script unzips the xlsx, pretty-prints every XML and `.rels` file, and prints a categorized inventory of key files plus a warning if high-risk content is detected (VBA, pivot tables, charts).

Read the printed output carefully before proceeding. If the script reports `xl/vbaProject.bin` or `xl/pivotTables/`, follow the constraints in Section 7.

### Step 2 — Reconnaissance

Map the structure before touching anything.

**Identify sheet names and their XML files:**

```
xl/workbook.xml  →  <sheet name="Revenue" sheetId="1" r:id="rId1"/>
xl/_rels/workbook.xml.rels  →  <Relationship Id="rId1" Target="worksheets/sheet1.xml"/>
```

The sheet named "Revenue" lives in `xl/worksheets/sheet1.xml`. Always resolve this mapping before editing a worksheet.

**Understand the shared strings table:**

```bash
# Count existing entries in xl/sharedStrings.xml
grep -c "<si>" /tmp/xlsx_work/xl/sharedStrings.xml
```

Every text cell uses a zero-based index into this table. Know the current count before appending.

**Understand the styles table:**

```bash
# Count existing cellXfs entries
grep -c "<xf " /tmp/xlsx_work/xl/styles.xml
```

New style slots are appended after existing ones. The index of the first new slot = current count.

**Scan for high-risk XML regions in the target worksheet:**

Look for these elements in the target `sheet*.xml` before editing:

- `<mergeCell>` — merged cell ranges; row/column insertion shifts these
- `<conditionalFormatting>` — condition ranges; row/column insertion shifts these
- `<dataValidations>` — validation ranges; row/column insertion shifts these
- `<tableParts>` — table definitions; row insertion inside a table needs `<tableColumn>` updates
- `<sparklineGroups>` — sparklines; preserve without modification

### Step 3 — Map Intent to Minimal XML Changes

Before writing a single character, produce a written list of exactly which XML nodes change. This prevents scope creep.

| User intent | Files to change | Nodes to change |
|-------------|----------------|-----------------|
| Change a cell's numeric value | `xl/worksheets/sheetN.xml` | `<v>` inside target `<c>` |
| Change a cell's text | `xl/sharedStrings.xml` (append) + `xl/worksheets/sheetN.xml` | New `<si>`, update cell `<v>` index |
| Change a cell's formula | `xl/worksheets/sheetN.xml` | `<f>` text inside target `<c>` |
| Add a new data row at the bottom | `xl/worksheets/sheetN.xml` + possibly `xl/sharedStrings.xml` | Append `<row>` element |
| Apply a new style to cells | `xl/styles.xml` + `xl/worksheets/sheetN.xml` | Append `<xf>` in `<cellXfs>`, update `s` attribute on `<c>` |
| Rename a sheet | `xl/workbook.xml` | `name` attribute on `<sheet>` element |
| Rename a sheet (with cross-sheet formulas) | `xl/workbook.xml` + all `xl/worksheets/*.xml` | `name` attribute + `<f>` text referencing old name |

### Step 4 — Execute Changes

Use the Edit tool. Edit the minimum. Never rewrite whole files.

See Section 4 for precise XML patterns for each operation type.

### Step 5 — Cascade Check

After any change that shifts row or column positions, audit all affected XML regions. See Section 5.

### Step 6 — Pack and Validate

```bash
python3 SKILL_DIR/scripts/xlsx_pack.py /tmp/xlsx_work/ output.xlsx
python3 SKILL_DIR/scripts/formula_check.py output.xlsx
```

The pack script validates XML well-formedness before creating the ZIP. Fix any reported parse errors before packing. After packing, run `formula_check.py` to confirm no formula errors were introduced.

---

