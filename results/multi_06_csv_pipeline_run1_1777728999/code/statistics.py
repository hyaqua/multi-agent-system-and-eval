"""
Statistics module – computes summary statistics for numeric columns
and top-N frequent values for text columns.
"""

import statistics as stats
from collections import Counter
from datetime import datetime
from typing import Any


def compute_numeric_stats(values: list) -> dict:
    """
    Compute summary statistics for a list of numeric values.

    Args:
        values: List of numeric values (int/float) with possible None entries.

    Returns:
        Dict with keys: count, mean, median, min, max, stdev or None values.
    """
    clean = [v for v in values if v is not None]

    if not clean:
        return {
            'count': 0,
            'mean': None,
            'median': None,
            'min': None,
            'max': None,
            'stdev': None,
        }

    floats = [float(v) for v in clean]
    result = {
        'count': len(floats),
        'mean': round(stats.mean(floats), 4),
        'median': round(stats.median(floats), 4),
        'min': min(floats),
        'max': max(floats),
        'stdev': None,
    }

    if len(floats) >= 2:
        try:
            result['stdev'] = round(stats.stdev(floats), 4)
        except stats.StatisticsError:
            result['stdev'] = None

    return result


def compute_text_frequencies(values: list, top_n: int = 5) -> list:
    """
    Compute the top-N most frequent values for a text column.

    Args:
        values: List of text values (strings) with possible None entries.
        top_n: Number of top frequent values to return.

    Returns:
        List of (value, count) tuples, sorted by frequency descending.
    """
    non_none = [v for v in values if v is not None]
    counter = Counter(non_none)
    return counter.most_common(top_n)


def compute_date_stats(values: list) -> dict:
    """
    Compute summary statistics for a date column.

    Args:
        values: List of datetime values with possible None entries.

    Returns:
        Dict with keys: count, min, max.
    """
    clean = [v for v in values if v is not None]

    if not clean:
        return {
            'count': 0,
            'min': None,
            'max': None,
        }

    return {
        'count': len(clean),
        'min': min(clean),
        'max': max(clean),
    }


def compute_all_statistics(header: list, rows: list, type_map: dict) -> dict:
    """
    Compute statistics for all columns based on their types.

    Args:
        header: List of column names.
        rows: List of typed row dicts.
        type_map: Dict mapping column_name -> type_string.

    Returns:
        Dict with 'numeric_stats', 'text_frequencies', 'date_stats'.
    """
    numeric_stats = {}
    text_frequencies = {}
    date_stats = {}

    for col in header:
        values = [row.get(col) for row in rows]
        col_type = type_map.get(col, 'text')

        if col_type in ('int', 'float'):
            numeric_stats[col] = compute_numeric_stats(values)
        elif col_type == 'date':
            date_stats[col] = compute_date_stats(values)
        else:
            text_frequencies[col] = compute_text_frequencies(values)

    return {
        'numeric_stats': numeric_stats,
        'text_frequencies': text_frequencies,
        'date_stats': date_stats,
    }
