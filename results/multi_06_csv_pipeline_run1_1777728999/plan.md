# Revised Implementation Plan: CSV Data Pipeline and Reporting Tool

**Revision Notes**  
- The pipeline **must** perform joins on raw (string) data **before** any type conversion, otherwise date keys break and type detection fails.  
- Duplicate key handling in joins now keeps the **last** row, with a warning (previously first).  
- All occurrences of a `statistics.py` module are removed; statistics computations live only in `stat_calc.py`.

---

## 1. File Structure and Responsibilities

- **`csv_pipeline.py`** – Main entry point. Parses CLI arguments, enforces correct pipeline order: raw loading → join (if requested) → type detection → filter → sort → statistics → reporting.
- **`reader.py`** – CSV reading, validation, handling of ragged rows, missing‑value counting. Returns a list of **raw‑string** dictionaries.
- **`operations.py`** – Row filtering, sorting, and **raw‑string join**. The join function reads the secondary file itself (via `reader.py`) and merges using the original string keys.
- **`type_detector.py`** – Automatic column type detection and **in‑place** conversion of raw strings to typed values. Must run **after** any join and on a dataset containing only raw strings.
- **`stat_calc.py`** – Summary statistics for numeric columns and top‑5 frequent values for text columns, using `statistics` from the standard library.
- **`reporter.py`** – Formatted text tables and CSV output.

All modules use only the Python standard library and must pass `flake8` with no unused imports.

---

## 2. Architecture and Data Flow (Corrected Order)

1. **CLI parsing** with `argparse`.  
   - Positional: one or more CSV file paths (`files`).  
   - Optional: `--filter`, `--sort`, `--sort-desc`, `--join-key`, `--join-file`, `--output`.

2. **Raw data loading** (`reader.py`)  
   - All input CSVs are read using `csv.DictReader`. Cell values remain as strings.  
   - Empty/missing indicators (`''`, `'NA'`, `'N/A'`, `'None'`, `'null'`) are replaced by `None` and counted per column.  
   - Rows whose length does not match the header trigger a warning and are padded/truncated.  
   - **All primary rows are combined into one list of raw‑string dictionaries.**

3. **Join (if requested)** – **executed here, on the raw dataset**  
   - The secondary file (`--join-file`) is loaded with the same `reader` module, yielding another list of raw‑string dictionaries.  
   - A lookup dictionary is built from the secondary rows, keyed by the exact raw string from `--join-key`. If a key appears more than once, the **last** occurrence overwrites earlier ones, and a warning is issued.  
   - For each primary row, the corresponding raw join‑key value is used to find a match. When a match exists, the two raw dictionaries are merged:  
     * Primary columns are kept.  
     * Secondary columns are added; name clashes (except the join key) are resolved by prefixing with `right_`.  
     * Rows without a match are **dropped** (inner join).  
   - The result is a new list of raw‑string dictionaries, potentially with extra columns from the secondary file. **No type conversion has occurred at this point.**

4. **Type detection and conversion** (`type_detector.py`)  
   - Receives the (possibly joined) list of raw‑string dictionaries.  
   - For every column, attempts `int` → `float` → `datetime` (several common formats). The type that succeeds for the most non‑`None` values (≥80% threshold for dates) is assigned.  
   - Replaces the raw string in each row with the converted Python object. Columns that remain as `str` keep their original strings.  
   - Prints a summary of inferred column types.

5. **Filtering** (`operations.py`) – operates on the typed rows.  
   - Parses `--filter 'column>value'` with a regex.  
   - Coerces the literal to the column’s detected type, then uses the `operator` module to compare.

6. **Sorting** (`operations.py`) – operates on typed rows.  
   - `--sort column_name` and optional `--sort-desc`.  
   - `None` values are placed at the end using a key that returns `(is_not_none, value)`.

7. **Statistics** (`stat_calc.py`)  
   - For numeric columns: count, mean, median, min, max, stdev (using `statistics` module).  
   - For text columns: top‑5 most frequent non‑`None` values via `collections.Counter`.

8. **Reporting** (`reporter.py`)  
   - If `--output` is given, writes the final, typed rows to CSV with `csv.DictWriter`.  
   - Otherwise, prints a formatted text table to stdout, followed by missing‑value counts and computed statistics.

> **Key rule**: Steps 3, 4 must happen **before** type detection. The join implementation is isolated in `operations.join_csvs(primary_raw, join_key, join_file)`, which itself calls `reader` for the secondary file and returns raw‑string rows.

---

## 3. Implementation Order (Adjusted)

1. **`reader.py`** – Robust CSV reading, handling all edge cases.
2. **`operations.py`** – Filter, sort, and **raw‑string join** logic. The join function must be written to expect raw data and to return raw data.
3. **`type_detector.py`** – Column type inference and conversion; must assume input rows are all strings.
4. **`stat_calc.py`** – Statistics and frequency counts (imports standard library `statistics`).
5. **`reporter.py`** – Table formatting and CSV output.
6. **`csv_pipeline.py`** – CLI orchestration that respects the correct order:  
   `reader` → `join` (if needed) → `type_detector` → `filter` (optional) → `sort` (optional) → `stat_calc` → `reporter`.

---

## 4. Standard Library Modules

- `argparse`, `csv`, `statistics`, `collections`, `datetime`, `re`, `os.path`, `itertools`, `warnings` – no third‑party libraries.

---

## 5. Detailed Feature Updates

### Merge (Join) Two CSV Files – Corrected

- **Flags**: `--join-key` (string) and `--join-file` (path).  
- **Procedure** (inside `operations.py`):  
  1. Read secondary file with `reader.py` (returns raw strings).  
  2. Build lookup dict: for each secondary row, `key = raw_value[join_key]`. If key already present, overwrite (last wins) and warn.  
  3. For each primary row, get its raw `join_key` value; if present in lookup, create a merged raw dict.  
     - Clashing column names (other than `join_key`): prefix with `right_`.  
  4. Return the list of merged raw rows. Rows not matched are excluded.
- **Usage**: `csv_pipeline.py` calls `joined_raw = operations.join_csvs(primary_raw, args.join_key, args.join_file)` **immediately after reading primary files**. The result is then passed to `type_detector.detect_and_convert(joined_raw)`.

### Duplicate Key Handling in Join

- When multiple rows in the secondary file share the same join key value, the **last** row encountered overwrites earlier ones.  
- A `warnings.warn` message is emitted for each overwritten duplicate.

### Date Handling During Join

- Because the join is done on raw strings, a date column like `"2020-01-15"` in the primary matches exactly the same string in the secondary. No conversion to `datetime` and back occurs, avoiding mismatches.

### Type Detection After Join

- After the join, the dataset contains **only** raw strings (some may be `None`). `type_detector` works from scratch, treating all columns uniformly. Previously, type detection could encounter already‑converted `datetime` objects from the primary file, causing failures; this is now prevented by the strict ordering.

### CLI Argument Parsing

- Positional argument `files` uses `nargs='+'`. The exact error shown in the test output (`error: the following arguments are required: files`) occurs when no files are supplied – this is the intended behaviour (print usage, exit with code 2).

---

## 6. Code Quality Requirements

- No file named `statistics.py` – the module is `stat_calc.py`.  
- All modules pass `flake8` (unused imports removed).  
- The pipeline order is enforced at the entry‑point level: `csv_pipeline.py` will not call `type_detector` before a possible join.

---

## 7. Testing Strategy

- Unit tests for `operations.join_csvs` with string keys, including duplicate secondary keys and date‑string columns.  
- Integration test: full pipeline with `--join` and a date column, verifying the output report retains correct joins.  
- Static analysis with `flake8` to confirm no shadowing or unused imports.

This revised plan eliminates the race between type conversion and join, guarantees correct date‑key matches, and fixes the duplicate‑key semantics as requested.