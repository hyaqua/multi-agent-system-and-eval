"""CSV file reading with robust error handling."""

import csv
import sys
import warnings


def read_csv(path: str) -> list[dict]:
    """Read a CSV file and return rows as a list of dicts.

    Handles quoted fields, commas within fields, and inconsistent column counts.
    Missing columns are padded with empty strings; extra columns are ignored with
    a warning.
    """
    try:
        with open(path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            # DictReader.fieldnames is set from the first row
            fieldnames = reader.fieldnames
            if fieldnames is None:
                warnings.warn(f"File '{path}' appears to be empty.")
                return []
            rows = []
            for line_no, row in enumerate(reader, start=2):  # header is line 1
                # Detect column count mismatch
                raw_values = list(row.values())
                if len(raw_values) != len(fieldnames):
                    # We need to know the actual number of fields this row had.
                    # Re-read the line to get accurate count.
                    pass
                # Pad missing columns
                for f in fieldnames:
                    if f not in row:
                        row[f] = ""
                    elif row[f] is None:
                        row[f] = ""
                # Strip extra keys (shouldn't happen with DictReader normally)
                row_keys = set(row.keys())
                for f in list(row_keys):
                    if f not in fieldnames:
                        del row[f]
                rows.append(row)
            return rows
    except FileNotFoundError:
        print(f"Error: File not found — '{path}'", file=sys.stderr)
        sys.exit(1)
    except csv.Error as e:
        print(f"Error: Failed to parse CSV file '{path}': {e}", file=sys.stderr)
        sys.exit(1)


def read_csv_with_column_warnings(path: str) -> list[dict]:
    """Read CSV, emitting warnings for rows with inconsistent column counts."""
    try:
        with open(path, "r", newline="", encoding="utf-8") as fh:
            # Read the header line
            header_line = fh.readline()
            if not header_line:
                warnings.warn(f"File '{path}' appears to be empty.")
                return []

            # Re-open to use csv.reader for accurate column counts per row
            fh.seek(0)
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                return []

            fieldnames = [h.strip() for h in header]
            # Deduplicate fieldnames if needed
            seen = {}
            unique_fields = []
            for f in fieldnames:
                if f in seen:
                    seen[f] += 1
                    unique_fields.append(f"{f}_{seen[f]}")
                else:
                    seen[f] = 1
                    unique_fields.append(f)
            fieldnames = unique_fields

            rows = []
            for line_no, raw_row in enumerate(reader, start=2):
                if len(raw_row) != len(fieldnames):
                    if len(raw_row) < len(fieldnames):
                        warnings.warn(
                            f"Row {line_no} in '{path}' has {len(raw_row)} columns, "
                            f"expected {len(fieldnames)}. Padding with empty strings."
                        )
                        raw_row.extend([""] * (len(fieldnames) - len(raw_row)))
                    else:
                        warnings.warn(
                            f"Row {line_no} in '{path}' has {len(raw_row)} columns, "
                            f"expected {len(fieldnames)}. Ignoring extra columns."
                        )
                        raw_row = raw_row[:len(fieldnames)]
                row = {fieldnames[i]: (raw_row[i] if raw_row[i] is not None else "") for i in range(len(fieldnames))}
                rows.append(row)
            return rows
    except FileNotFoundError:
        print(f"Error: File not found — '{path}'", file=sys.stderr)
        sys.exit(1)
    except csv.Error as e:
        print(f"Error: Failed to parse CSV file '{path}': {e}", file=sys.stderr)
        sys.exit(1)


# Use the robust version by default
read_csv = read_csv_with_column_warnings
