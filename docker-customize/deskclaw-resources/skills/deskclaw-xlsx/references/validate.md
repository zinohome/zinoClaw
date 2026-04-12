# Formula Validation & Recalculation Guide

Ensure every formula in an xlsx file is provably correct before delivery. A file that opens without visible errors is not a passing file — only a file that has cleared both validation tiers is a passing file.

---

## Foundational Rules

- **Never declare PASS without running `formula_check.py` first.** Visual inspection of a spreadsheet is not validation.
- **Tier 1 (static) is mandatory in every scenario.** Tier 2 (dynamic) is mandatory when LibreOffice is available. If it is unavailable, you must state this explicitly in the report — you may not silently skip it.
- **Never use openpyxl with `data_only=True` to check formula values.** Opening and saving a workbook in `data_only=True` mode permanently replaces all formulas with their last cached values. Formulas cannot be recovered afterward.
- **Auto-fix only deterministic errors.** Any fix that requires understanding business logic must be flagged for human review.

---

## Two-Tier Validation Architecture

```
Tier 1 — Static Validation (XML scan, no external tools)
  │
  ├── Detect: all 7 Excel error types already cached in <v> elements
  ├── Detect: cross-sheet references pointing to nonexistent sheets
  ├── Detect: formula cells with t="e" attribute (error type marker)
  └── Tool: formula_check.py + manual XML inspection
        │
        ▼ (if LibreOffice is present)
Tier 2 — Dynamic Validation (LibreOffice headless recalculation)
  │
  ├── Executes all formulas via the LibreOffice Calc engine
  ├── Populates <v> cache values with real computed results
  ├── Exposes runtime errors invisible before recalculation
  └── Follow-up: re-run Tier 1 on the recalculated file
```

**Why two tiers?**

openpyxl and all Python xlsx libraries write formula strings (e.g. `=SUM(B2:B9)`) into `<f>` elements but do not evaluate them. A freshly generated file has empty `<v>` cache elements for every formula cell. This means:

- Tier 1 can only catch errors that are already encoded in the XML — either as `t="e"` cells or as structurally broken cross-sheet references.
- Tier 2 uses LibreOffice as the actual calculation engine, runs every formula, fills `<v>` with real results, and surfaces runtime errors (`#DIV/0!`, `#N/A`, etc.) that can only appear after computation.

Neither tier alone is sufficient. Together they cover the full correctability surface.

---

