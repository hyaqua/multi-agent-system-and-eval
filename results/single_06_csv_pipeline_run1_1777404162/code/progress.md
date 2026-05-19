STATUS: COMPLETE

## CSV Data Pipeline - Feature Checklist

All 13 required features have been implemented and tested:

1. **Accepts one or more CSV file paths as command-line arguments**
   - Supports multiple files which are concatenated together.
   - Tested with 2 files combining 10 + 3 = 13 rows.

2. **Reads and parses CSV files handling quoted fields and commas within fields correctly**
   - Uses Python's `csv` module with dialect sniffing.
   - Tested with `test_quoted.csv` containing values like "Widget, Blue" and "Doohickey, Black - Special Edition".

3. **Detects and reports column data types (numeric, text, date) automatically**
   - Type detection requires >=70% of non-empty values to match.
   - Supports 13 common date formats.
   - Correctly identifies `age`/`salary` as numeric, `hire_date` as date, `name`/`department` as text.

4. **Handles missing or empty values by reporting their count per column**
   - Reports "Empty/Missing: N" for every column in the summary report.
   - Tested with rows having empty salary (Henry) and empty hire_date (Iris).

5. **Computes summary statistics for numeric columns: count, mean, median, min, max, standard deviation**
   - Sample variance (n-1 denominator) used for standard deviation.
   - All statistics displayed with 4 decimal places.

6. **Shows the top 5 most frequent values for text columns**
   - Uses `collections.Counter.most_common(5)`.
   - Displays value and count.

7. **Supports filtering rows by a column value condition (e.g. --filter 'age>30')**
   - Supported operators: `>`, `<`, `>=`, `<=`, `=`, `!=`.
   - Type-aware comparison (numeric, date, text).
   - Reports how many rows were filtered: "10 rows → 6 rows".

8. **Supports sorting output by a specified column with --sort flag**
   - Type-aware sorting: numeric (by value), date (chronological), text (case-insensitive alpha).
   - Empty/null values sort to the beginning.

9. **Can merge two CSV files on a shared key column with a --join flag**
   - Format: `--join 'file.csv,key_column'`.
   - Left join: all left rows preserved, right columns filled with empty strings when no match.
   - Tested joining test_data.csv with test_dept.csv on 'department'.

10. **Outputs the processed result to a new CSV file with --output flag**
    - Writes standard CSV with headers and processed rows.
    - Combined with --filter and --sort successfully.

11. **Displays a formatted text table report to stdout by default**
    - ASCII table with borders, aligned columns, auto-width (capped at 30 chars).
    - Row count displayed below the table.

12. **Handles files with inconsistent column counts gracefully with a warning**
    - Prints WARNING to stderr when row lengths don't match the header.
    - Pads short rows with empty strings, truncates long rows.

13. **Shows an error message if an input file does not exist**
    - Prints "ERROR: File not found: <path>" to stderr and exits with code 1.
    - Also validated for --join files.

## Files Created
- `csv_pipeline.py` - Main tool (single file, standard library only)
- `test_data.csv` - Test data with mixed types and missing values
- `test_dept.csv` - Test data for joins, with quoted field containing comma
- `test_quoted.csv` - Test data for quoted fields with commas
- `test_inconsistent.csv` - Test data with inconsistent column counts
