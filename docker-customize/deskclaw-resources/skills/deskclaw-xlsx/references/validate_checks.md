## Tier 1 — Static Validation

Static validation requires no external tools. It works directly on the ZIP/XML structure of the xlsx file.

### Step 1: Run formula_check.py

**Standard (human-readable) output:**

```bash
python3 SKILL_DIR/scripts/formula_check.py /path/to/file.xlsx
```

**JSON output (for programmatic processing):**

```bash
python3 SKILL_DIR/scripts/formula_check.py /path/to/file.xlsx --json
```

**Single-sheet mode (faster for targeted checks):**

```bash
python3 SKILL_DIR/scripts/formula_check.py /path/to/file.xlsx --sheet Summary
```

**Summary mode (counts only, no per-cell detail):**

```bash
python3 SKILL_DIR/scripts/formula_check.py /path/to/file.xlsx --summary
```

Exit codes:
- `0` — no hard errors (PASS or PASS with heuristic warnings)
- `1` — hard errors detected, or file cannot be opened (FAIL)

#### What formula_check.py examines

The script opens the xlsx as a ZIP archive without using any Excel library. It reads `xl/workbook.xml` to enumerate sheet names and named ranges, reads `xl/_rels/workbook.xml.rels` to map each sheet to its XML file, then iterates every `<c>` element in every worksheet.

It performs five checks:

1. **Error-value detection**: If the cell has `t="e"`, its `<v>` element contains an Excel error string. The cell is recorded with its sheet name, cell reference (e.g. `C5`), the error value, and the formula text if present.

2. **Broken cross-sheet reference detection**: If the cell has an `<f>` element, the script extracts all sheet names referenced in the formula (both `SheetName!` and `'Sheet Name'!` syntax). Each name is compared against the list of sheets in `workbook.xml`. A mismatch is a broken reference.

3. **Unknown named-range detection (heuristic)**: Identifiers in formulas that are not function names, not cell references, and not found in `workbook.xml`'s `<definedNames>` are flagged as `unknown_name_ref` warnings. This is a heuristic — false positives are possible; always verify manually.

4. **Shared formula integrity**: Shared formula consumer cells (those with only `<f t="shared" si="N"/>`) are skipped for formula counting and cross-ref checks because they inherit the primary cell's formula. Only the primary cell (with `ref="..."` attribute and formula text) is checked and counted.

5. **Malformed error cells**: Cells with `t="e"` but no `<v>` child element are flagged as structural XML issues.

Hard errors (exit code 1): `error_value`, `broken_sheet_ref`, `malformed_error_cell`, `file_error`
Soft warnings (exit code 0): `unknown_name_ref` — must be verified manually but do not block delivery alone

#### Reading formula_check.py human-readable output

A clean file looks like this:

```
File   : /tmp/budget_2024.xlsx
Sheets : Summary, Q1, Q2, Q3, Q4, Assumptions
Formulas checked      : 312 distinct formula cells
Shared formula ranges : 4 ranges
Errors found          : 0

PASS — No formula errors detected
```

A file with errors looks like this:

```
File   : /tmp/budget_2024.xlsx
Sheets : Summary, Q1, Q2, Q3, Q4, Assumptions
Formulas checked      : 312 distinct formula cells
Shared formula ranges : 4 ranges
Errors found          : 4

── Error Details ──
  [FAIL] [Summary!C12] contains #REF! (formula: Q1!A0/Q1!A1)
  [FAIL] [Summary!D15] references missing sheet 'Q5'
         Formula: Q5!D15
         Valid sheets: ['Assumptions', 'Q1', 'Q2', 'Q3', 'Q4', 'Summary']
  [FAIL] [Q1!F8] contains #DIV/0!
  [WARN] [Q2!B10] uses unknown name 'GrowthAssumptions' (heuristic — verify manually)
         Formula: SUM(GrowthAssumptions)
         Defined names: ['RevenueRange', 'CostRange']

FAIL — 3 error(s) must be fixed before delivery
WARN — 1 heuristic warning(s) require manual review
```

Interpretation of each line:
- `[FAIL] [Summary!C12] contains #REF! (formula: Q1!A0/Q1!A1)` — The cell has `t="e"` and `<v>#REF!</v>`. The formula references row 0, which does not exist in Excel's 1-based system. This is an off-by-one error in a generated reference.
- `[FAIL] [Summary!D15] references missing sheet 'Q5'` — The formula contains `Q5!D15`, but no sheet named `Q5` exists in the workbook. The valid sheet list is provided for comparison.
- `[FAIL] [Q1!F8] contains #DIV/0!` — This cell's `<v>` is already an error value (the file was previously recalculated). The formula divided by zero.
- `[WARN] [Q2!B10] uses unknown name 'GrowthAssumptions'` — The identifier `GrowthAssumptions` appears in the formula but is not in `<definedNames>`. This may be a typo or a name that was accidentally omitted. It is a heuristic warning — verify manually. The warning alone does not block delivery.

#### Reading formula_check.py JSON output

```json
{
  "file": "/tmp/budget_2024.xlsx",
  "sheets_checked": ["Summary", "Q1", "Q2", "Q3", "Q4", "Assumptions"],
  "formula_count": 312,
  "shared_formula_ranges": 4,
  "error_count": 4,
  "errors": [
    {
      "type": "error_value",
      "error": "#REF!",
      "sheet": "Summary",
      "cell": "C12",
      "formula": "Q1!A0/Q1!A1"
    },
    {
      "type": "broken_sheet_ref",
      "sheet": "Summary",
      "cell": "D15",
      "formula": "Q5!D15",
      "missing_sheet": "Q5",
      "valid_sheets": ["Assumptions", "Q1", "Q2", "Q3", "Q4", "Summary"]
    },
    {
      "type": "error_value",
      "error": "#DIV/0!",
      "sheet": "Q1",
      "cell": "F8",
      "formula": null
    },
    {
      "type": "unknown_name_ref",
      "sheet": "Q2",
      "cell": "B10",
      "formula": "SUM(GrowthAssumptions)",
      "unknown_name": "GrowthAssumptions",
      "defined_names": ["RevenueRange", "CostRange"],
      "note": "Heuristic check — verify manually if this is a false positive"
    }
  ]
}
```

Field reference:

| Field | Meaning |
|-------|---------|
| `type: "error_value"` | Cell has `t="e"` — an Excel error is stored in the `<v>` element |
| `type: "broken_sheet_ref"` | Formula references a sheet name not present in workbook.xml |
| `type: "unknown_name_ref"` | Formula references an identifier not in `<definedNames>` (heuristic, soft warning) |
| `type: "malformed_error_cell"` | Cell has `t="e"` but no `<v>` child — structural XML problem |
| `type: "file_error"` | The file could not be opened (bad ZIP, not found, etc.) |
| `sheet` | The sheet where the error was found |
| `cell` | Cell reference in A1 notation |
| `formula` | The full formula text from the `<f>` element (null if not present) |
| `error` | The error string from `<v>` (for `error_value` type) |
| `missing_sheet` | The sheet name extracted from the formula that does not exist |
| `valid_sheets` | All sheet names actually present in workbook.xml |
| `unknown_name` | The identifier that was not found in `<definedNames>` |
| `defined_names` | All named ranges actually present in workbook.xml |
| `shared_formula_ranges` | Count of shared formula definitions (top-level `<f t="shared" ref="...">` elements) |

### Step 2: Manual XML inspection

When formula_check.py reports errors, unpack the file to inspect the raw XML:

```bash
python3 SKILL_DIR/scripts/xlsx_unpack.py /path/to/file.xlsx /tmp/xlsx_inspect/
```

Navigate to the worksheet file for the reported sheet. The sheet-to-file mapping is in `xl/_rels/workbook.xml.rels`. For example, if `rId1` maps to `worksheets/sheet1.xml`, then sheet1.xml is the file for the sheet with `r:id="rId1"` in `xl/workbook.xml`.

For each reported error cell, locate the `<c r="CELLREF">` element and examine:

**For `error_value` errors:**
```xml
<!-- This is what an error cell looks like in XML -->
<c r="C12" t="e">
  <f>Q1!C10/Q1!C11</f>
  <v>#DIV/0!</v>
</c>
```

Ask:
- Is the `<f>` formula syntactically correct?
- Does the cell reference in the formula point to a row/column that exists?
- If it is a division, is it possible the denominator cell is empty or zero?

**For `broken_sheet_ref` errors:**

Check `xl/workbook.xml` for the actual sheet list:

```xml
<sheets>
  <sheet name="Summary" sheetId="1" r:id="rId1"/>
  <sheet name="Q1"      sheetId="2" r:id="rId2"/>
  <sheet name="Q2"      sheetId="3" r:id="rId3"/>
</sheets>
```

Sheet names are case-sensitive. `q1` and `Q1` are different sheets. Compare the name in the formula exactly against the names here.

### Step 3: Cross-sheet reference audit (multi-sheet workbooks)

For workbooks with 3 or more sheets, run a broader cross-reference audit after unpacking:

```bash
# Extract all formulas containing cross-sheet references
grep -h "<f>" /tmp/xlsx_inspect/xl/worksheets/*.xml | grep "!"

# List all actual sheet names from workbook.xml
grep -o 'name="[^"]*"' /tmp/xlsx_inspect/xl/workbook.xml | grep -v sheetId
```

Every sheet name appearing in formulas (in the form `SheetName!` or `'Sheet Name'!`) must appear in the workbook sheet list. If any do not match, that is a broken reference even if formula_check.py did not catch it (which can happen with shared formulas where only the primary cell is examined).

To check shared formulas specifically, look for `<f t="shared" ref="...">` elements:

```xml
<!-- Shared formula: defined on D2, applied to D2:D100 -->
<c r="D2"><f t="shared" ref="D2:D100" si="0">Q1!B2*C2</f><v></v></c>

<!-- Shared formula consumers: only si is present, no formula text -->
<c r="D3"><f t="shared" si="0"/><v></v></c>
```

formula_check.py reads the formula text from the primary cell (`D2` above). The referenced sheet `Q1` in that formula applies to the entire range `D2:D100`. If the sheet is broken, all 99 rows are broken even though they appear as empty `<f>` elements.

---

## Tier 2 — Dynamic Validation (LibreOffice Headless)

### Check LibreOffice availability

```bash
# Check macOS (typical install location)
which soffice
/Applications/LibreOffice.app/Contents/MacOS/soffice --version

# Check Linux
which libreoffice || which soffice
libreoffice --version
```

If neither command returns a path, LibreOffice is not installed. Record "Tier 2: SKIPPED — LibreOffice not available" in the report and proceed to delivery with Tier 1 results only.

### Install LibreOffice (if permitted in the environment)

macOS:
```bash
brew install --cask libreoffice
```

Ubuntu/Debian:
```bash
sudo apt-get install -y libreoffice
```

### Run headless recalculation

Use the dedicated recalculation script. It handles binary discovery across macOS and Linux, works from a temporary copy of the input (preserving the original), and provides structured output and exit codes compatible with the validation pipeline.

```bash
# Check LibreOffice availability first
python3 SKILL_DIR/scripts/libreoffice_recalc.py --check

# Run recalculation (default timeout: 60s)
python3 SKILL_DIR/scripts/libreoffice_recalc.py /path/to/input.xlsx /tmp/recalculated.xlsx

# For large or complex files, extend the timeout
python3 SKILL_DIR/scripts/libreoffice_recalc.py /path/to/input.xlsx /tmp/recalculated.xlsx --timeout 120
```

Exit codes from `libreoffice_recalc.py`:
- `0` — recalculation succeeded, output file written
- `2` — LibreOffice not found (note as SKIPPED in report; not a hard failure)
- `1` — LibreOffice found but failed (timeout, crash, malformed file)

**What the script does internally:**

LibreOffice's `--convert-to xlsx` command opens the file using the full Calc engine with the `--infilter="Calc MS Excel 2007 XML"` filter, executes every formula, writes computed values into the `<v>` cache elements, and saves the output. This is the closest server-side equivalent of "open in Excel and press Save." The script also passes `--norestore` to prevent LibreOffice from attempting to restore previous sessions, which can cause hangs in automated environments.

**If LibreOffice is not installed:**

macOS:
```bash
brew install --cask libreoffice
```

Ubuntu/Debian:
```bash
sudo apt-get install -y libreoffice
```

**If the script times out (libreoffice_recalc.py exits with code 1 and "timed out" message):**

Record "Tier 2: TIMEOUT — LibreOffice did not complete within Ns" in the report. Do not retry in a loop. Investigate whether the file has circular references or extremely large data ranges.

### Re-run Tier 1 after recalculation

After LibreOffice recalculation, the `<v>` elements contain real computed values. Errors that were invisible before (because `<v>` was empty in a freshly generated file) now appear as `t="e"` cells with actual error strings.

```bash
python3 SKILL_DIR/scripts/formula_check.py /tmp/recalculated.xlsx
```

This second Tier 1 pass is the definitive runtime error check. Any errors it finds are real calculation failures that must be fixed.

---

