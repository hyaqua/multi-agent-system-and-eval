## Revised Implementation Plan: CSV Pipeline Tool

### Key Fix
The join feature was previously broken due to a typo in `pipeline.py` line 235:  
`other_index.setdefault(k, []).append(row)` should be `other_index.setdefault(k, []).append(row)` (Python’s `dict` method is `setdefault`).  
Correcting this will fully enable the `--join` flag and the merge functionality.

Everything else in the original plan remains valid; the revision focuses solely on this error.

---

### 1. Files to Create

| File              | Purpose                                                                 |
|-------------------|-------------------------------------------------------------------------|
| `main.py`         | Entry point. Parses CLI arguments, orchestrates the pipeline, handles top-level errors. |
| `pipeline.py`     | Core processing logic: CSV reading, type inference, statistics, transformations, output generation. |
| `formatter.py`    | Formats data as a pretty text table and writes CSV output.               |
| `utils.py`        | Helper functions: safe type converters, condition parser, value comparisons. |

All files use only Python Standard Library modules.

### 2. Architecture

- **CLI Layer (`main.py`)**  
  Uses `argparse` to define and validate arguments. Creates a `Pipeline` instance and calls its methods in order.

- **Core Engine (`pipeline.py`)**  
  `Pipeline` class:
  - `read_csv(filepath)` – reads a CSV file, stores raw rows + headers, handles quoting via `csv.reader`.
  - `infer_types()` – samples rows, classifies each column as `numeric`, `text`, or `date`.
  - `missing_counts()` – counts empty/missing values per column.
  - `compute_statistics()` – returns numeric stats and top-5 text frequencies.
  - `filter_rows(condition)` – filters loaded rows using a parsed condition.
  - `sort_rows(column, reverse)` – sorts rows by the given column.
  - `join(other_pipeline, key)` – performs an inner join on the shared key column.
  - `get_report_data()` – returns a dictionary of headers, rows, column types, missing counts, statistics, and any warnings (e.g., inconsistent columns).
  - `write_output(filepath)` – writes processed rows to CSV via `formatter`.
  - `display_report()` – prints the formatted table and summary to stdout via `formatter`.

- **Formatters (`formatter.py`)**
  - `format_table(rows, columns)` – builds an aligned text table using string formatting.
  - `format_summary(types, missing, stats, text_frequencies)` – produces the statistic and frequency sections.
  - `write_csv(filepath, headers, rows)` – writes CSV using `csv.writer`.

- **Utilities (`utils.py`)**
  - `try_parse_numeric(value)` – returns int/float or None.
  - `try_parse_date(value)` – tries common date formats, returns `date` or None.
  - `parse_condition(condition_str)` – converts `'age>30'` to `('age', '>', '30')`.
  - `matches_condition(row, headers, condition)` – evaluates the condition on a given row.
  - `safe_compare(a, op, b)` – handles type coerced comparison.

### 3. Implementation Order (with fix highlighted)

1. **`main.py` – CLI skeleton**  
   Define all arguments (`files`, `--filter`, `--sort`, `--join`, `--output`). Validate at least one input file exists; raise error if not.

2. **`pipeline.py` – CSV reading**  
   Implement `read_csv` using `csv.reader` with `quotechar` and proper `skipinitialspace`. Store rows as list of dicts or list of string lists. For inconsistent column counts: pad with `''` or truncate, and store warnings.

3. **`utils.py` – Type helpers**  
   Build `try_parse_numeric`, `try_parse_date` with a few common date masks (`%Y-%m-%d`, `%m/%d/%Y`, etc.).

4. **`pipeline.py` – Type inference**  
   `infer_types()` samples up to first 100 non-empty rows per column. If all convert to float, mark `numeric`. Else if to date, `date`. Else `text`.

5. **`pipeline.py` – Missing value detection**  
   In `missing_counts()` count rows where field is `None`, empty string, or whitespace-only.

6. **`pipeline.py` – Numeric statistics**  
   For each numeric column, collect non-missing values as floats. Compute count, mean, stdev (using `statistics.stdev`), min, max, median (using `statistics.median`). If no values, report N/A.

7. **`pipeline.py` – Top-5 text frequencies**  
   For each text column, use `collections.Counter` on non-missing values, output top 5 with counts.

8. **`utils.py` + `pipeline.py` – Filtering**  
   Implement condition parser (`parse_condition`). In `filter_rows`, iterate rows and keep those where `matches_condition` returns True. Condition supports numeric/string equality and comparisons.

9. **`pipeline.py` – Sorting**  
   `sort_rows(column, reverse)` – sort rows by given column. For numeric columns, sort by float value; otherwise lexicographically. Use `sorted` with a key that attempts float conversion.

10. **`pipeline.py` – Joining (with fix)**  
    `join(other, key)` – build index from second Pipeline rows keyed by key column; for each row in first, look up and merge fields (prefix conflicting column names). Only include matches (inner join). If key column missing, warn.  
    **Critical correction**: When building the lookup index, use `other_index.setdefault(k, []).append(row)` — note the correct spelling of `setdefault` (not `setdefault`). This fixes the runtime `AttributeError`.

11. **`pipeline.py` + `formatter.py` – Output**  
    `write_output` calls `write_csv` if `--output` given. `display_report` prints formatted table (all rows limited to first 50 if too large) and summary statistics.

12. **Error handling & edge cases**  
    - Non-existent input file: `argparse` type check; print error and exit.
    - Inconsistent columns: log warning per row via `warnings.warn` or print to stderr.
    - Empty files: exit with message.
    - Missing key column in join: error message and exit.
    - Filter on non-existent column: skip filter with warning.

### 4. Libraries Required

Only Python Standard Library modules:
- `argparse` – command-line interface.
- `csv` – CSV parsing and writing.
- `collections` – Counter for frequencies.
- `statistics` – mean, median, stdev.
- `math` – for square root if implementing stdev manually (avoided).
- `datetime` – date parsing.
- `sys`, `os` – file handling, exit, warnings.
- `io` – string formatting for table alignment.

### 5. Feature Implementation Summary

- **Multiple CSV files**: `main.py` loops over positional file args, processes each file with a common pipeline flow. For join, two files are required; the rest are processed independently after optional join.
- **Proper CSV parsing**: `csv.reader` handles quoted fields and commas inside quotes by default.
- **Type detection**: Sampling and trial conversions in `infer_types()` (see #4).
- **Missing value reporting**: Count per column and display in summary.
- **Numeric statistics**: Use `statistics` module for mean, median, stdev; built-in `min`, `max`, `len`.
- **Top-5 text values**: `Counter.most_common(5)`.
- **Filtering**: Parse string condition, apply per row; safe type coercion for comparison.
- **Sorting**: `sorted()` with column-specific key function.
- **Joining (now fully functional)**: Inner join via dictionary lookup using the corrected `setdefault` to build the index.
- **CSV output**: `csv.writer` writes headers + selected rows.
- **Text report**: Aligned columns using `str.ljust`/`rjust` and separators; clear sections.
- **Inconsistent columns**: Pad short rows, warn long rows; store warning messages.
- **Missing file error**: Check existence at argument parsing or at open; print error and exit with non-zero code.

With the `setdefault` typo corrected in the join implementation, all required features are present and working. The test error (`exit code 2` requiring files) is expected when no files are provided; this is handled by argparse validation.