"""
CSV Reader module with robust parsing, validation, and missing value handling.
"""

import csv
import os
import sys
import warnings


# Common missing value indicators
MISSING_INDICATORS = {'', 'NA', 'N/A', 'n/a', 'None', 'null', 'NULL', '-', 'nan', 'NaN'}


def read_csv(filepath: str) -> tuple:
    """
    Read a CSV file and return (header, rows, missing_counts).

    - Uses csv.reader for proper quoted field handling.
    - First row is treated as the header.
    - Rows with inconsistent column counts trigger a warning but are included.
    - Missing/empty values are mapped to None and counted.

    Args:
        filepath: Path to the CSV file.

    Returns:
        Tuple of (header: list[str], rows: list[dict], missing_counts: dict[str, int])

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Input file not found: {filepath}")

    with open(filepath, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f, quotechar='"', skipinitialspace=True)
        try:
            header = next(reader)
        except StopIteration:
            # Empty file
            return [], [], {}

        # Strip whitespace from header names
        header = [h.strip() for h in header]
        header_len = len(header)

        missing_counts = {col: 0 for col in header}
        rows = []

        for row_num, raw_row in enumerate(reader, start=2):  # start at 2 because line 1 is header
            # Handle inconsistent column counts
            if len(raw_row) != header_len:
                warnings.warn(
                    f"Row {row_num} in '{filepath}' has {len(raw_row)} fields "
                    f"(expected {header_len}). Padding/truncating.",
                    RuntimeWarning
                )
                if len(raw_row) < header_len:
                    raw_row = raw_row + [None] * (header_len - len(raw_row))
                else:
                    raw_row = raw_row[:header_len]

            # Build dict and detect missing values
            row_dict = {}
            for i, col_name in enumerate(header):
                val = raw_row[i].strip() if raw_row[i] is not None else None
                if val is None or val in MISSING_INDICATORS:
                    row_dict[col_name] = None
                    missing_counts[col_name] += 1
                else:
                    row_dict[col_name] = val

            rows.append(row_dict)

    return header, rows, missing_counts


def read_csv_for_join(filepath: str, key_column: str) -> dict:
    """
    Read a CSV and build a lookup dictionary keyed by a specified column.
    Used for join operations. Only the first row per key is kept.

    Args:
        filepath: Path to the CSV file.
        key_column: Column name to use as the dictionary key.

    Returns:
        Tuple of (lookup_dict, header, rows)
        where lookup_dict maps key_value -> row_dict
    """
    header, rows, _ = read_csv(filepath)

    if key_column not in header:
        raise ValueError(f"Key column '{key_column}' not found in '{filepath}'.")

    lookup = {}
    for row in rows:
        key_val = row.get(key_column)
        if key_val is not None and key_val not in lookup:
            lookup[key_val] = row

    return lookup, header, rows
