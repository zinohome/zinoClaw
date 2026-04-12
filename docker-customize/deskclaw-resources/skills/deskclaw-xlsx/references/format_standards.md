# Financial Formatting & Output Standards — Complete Agent Guide

> This document is the complete reference manual for the agent when applying professional financial formatting to xlsx files. All operations target direct XML surgery on `xl/styles.xml` without using openpyxl. Every operational step provides ready-to-use XML snippets.

---

## 1. When to Use This Path

This document (FORMAT path) applies to the following two scenarios:

**Scenario A — Dedicated Formatting of an Existing File**
The user provides an existing xlsx file and requests that financial modeling formatting standards be applied or unified. The starting point is to unpack the file, audit the existing `styles.xml`, then append missing styles and batch-update cell `s` attributes. No cell values or formulas are modified.

**Scenario B — Applying Format Standards After CREATE/EDIT**
After completing data entry or formula writing, formatting is applied as the final step. At this point, `styles.xml` may come from the minimal_xlsx template (which pre-defines 13 style slots) or from a user file. In either case, follow the principle of "append only, never modify existing xf entries."

**Not applicable**: Reading or analyzing file contents only (use the READ path); modifying formulas or data (use the EDIT path).

---

## 2. Financial Format Semantic System

### 2.1 Font Color = Cell Role (Color = Role)

The primary convention of financial modeling: **font color encodes the cell's role, not decoration**. A reviewer can glance at colors to determine which cells are adjustable parameters and which are model-calculated results. This is an industry-wide convention (followed by investment banks, the Big Four, and corporate finance teams).

| Role | Font Color | AARRGGBB | Use Case |
|------|-----------|----------|----------|
| Hard-coded input / assumption | Blue | `000000FF` | Growth rates, discount rates, tax rates, and other user-modifiable parameters |
| Formula / calculated result | Black | `00000000` | All cells containing a `<f>` element |
| Same-workbook cross-sheet reference | Green | `00008000` | Cells whose formula starts with `SheetName!` |
| External file link | Red | `00FF0000` | Cells whose formula contains `[FileName.xlsx]` (flagged as fragile links) |
| Label / text | Black (default) | theme color | Row labels, category headings |
| Key assumption requiring review | Blue font + yellow fill | Font `000000FF` / Fill `00FFFF00` | Provisional values, parameters pending confirmation |

**Decision tree**:
```
Does the cell contain a <f> element?
  +-- Yes -> Does the formula start with [FileName]?
  |           +-- Yes -> Red (external link)
  |           +-- No  -> Does the formula contain SheetName!?
  |                       +-- Yes -> Green (cross-sheet reference)
  |                       +-- No  -> Black (same-sheet formula)
  +-- No  -> Is the value a user-adjustable parameter?
              +-- Yes -> Blue (input/assumption)
              +-- No  -> Black default (label)
```

**Strictly prohibited**: Blue font + `<f>` element coexisting (color role contradiction — must be corrected).

### 2.2 Number Format Matrix

| Data Type | formatCode | numFmtId | Display Example | Applicable Scenario |
|-----------|-----------|----------|-----------------|---------------------|
| Standard currency (whole dollars) | `$#,##0;($#,##0);"-"` | 164 | $1,234 / ($1,234) / - | P&L, balance sheet amount rows |
| Standard currency (with cents) | `$#,##0.00;($#,##0.00);"-"` | 169 | $1,234.56 / ($1,234.56) / - | Unit prices, detailed costs |
| Thousands (K) | `#,##0,"K"` | 171 | 1,234K | Simplified display for management reports |
| Millions (M) | `#,##0,,"M"` | 172 | 1M | Macro-level summary rows |
| Percentage (1 decimal) | `0.0%` | 165 | 12.5% | Growth rates, gross margins |
| Percentage (2 decimals) | `0.00%` | 170 | 12.50% | IRR, precise interest rates |
| Multiple / valuation multiplier | `0.0x` | 166 | 8.5x | EV/EBITDA, P/E |
| Integer (thousands separator) | `#,##0` | 167 | 12,345 | Employee count, unit quantities |
| Year | `0` | 1 (built-in, no declaration needed) | 2024 | Column header years, prevents 2,024 |
| Date | `m/d/yyyy` | 14 (built-in, no declaration needed) | 3/21/2026 | Timelines |
| General text | General | 0 (built-in, no declaration needed) | — | Label rows, cells with no format requirement |

numFmtId 169–172 are custom formats that need to be appended beyond the 4 formats (164–167) pre-defined in the minimal_xlsx template. When appending, assign IDs according to the rules (see Section 3.4).

**Built-in format IDs do not need to be declared in `<numFmts>`** (IDs 0–163 are built into Excel/LibreOffice; simply reference the numFmtId in `<xf>`):

| numFmtId | formatCode | Description |
|----------|-----------|-------------|
| 0 | General | General format |
| 1 | `0` | Integer, no thousands separator (use this ID for years) |
| 3 | `#,##0` | Thousands-separated integer (no decimals) |
| 9 | `0%` | Percentage integer |
| 10 | `0.00%` | Percentage with two decimals |
| 14 | `m/d/yyyy` | Short date |

### 2.3 Negative Number Display Standards

Financial reports have two mainstream conventions for negative numbers — choose one and **maintain consistency** throughout the entire workbook:

**Parenthetical style (investment banking standard, recommended for external deliverables)**

```
Positive: $1,234    Negative: ($1,234)    Zero: -
formatCode: $#,##0;($#,##0);"-"
```

**Red minus sign style (suitable for internal operational analysis reports)**

```
Positive: $1,234    Negative: -$1,234 (red)
formatCode: $#,##0;[Red]-$#,##0;"-"
```

Rule: Once a style is determined, maintain it across the entire workbook. Do not mix two negative number display styles within the same workbook.

### 2.4 Zero Value Display Standards

In financial models, "0" and "no data" have different semantics and should be visually distinct:

| Scenario | Recommended Display | formatCode Third Segment |
|----------|-------------------|--------------------------|
| Sparse matrix (most rows have zero-value periods) | Dash `-` | `"-"` |
| Quantity counts (zero itself is meaningful) | `0` | `0` or omit |
| Placeholder row (explicitly empty) | Leave blank | Do not write to cell |

Four-segment format syntax: `positive format;negative format;zero value format;text format`

Zero as dash: `$#,##0;($#,##0);"-"`
Zero preserved as 0: `#,##0;(#,##0);0`

---

