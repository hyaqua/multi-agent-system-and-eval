"""Column type detection, statistics, and frequency analysis."""

import datetime
import statistics
from collections import Counter

# Common date formats to try
DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
]


def _parse_date(value: str) -> datetime.date | datetime.datetime | None:
    """Try to parse a string as a date using common formats."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    # Try ISO format via fromisoformat (Python 3.7+)
    try:
        # Try with time component first
        return datetime.datetime.fromisoformat(value).date()
    except (ValueError, TypeError):
        pass
    try:
        return datetime.date.fromisoformat(value)
    except (ValueError, TypeError):
        pass
    return None


def _is_int(value: str) -> bool:
    """Check if string represents an integer."""
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False


def _is_float(value: str) -> bool:
    """Check if string represents a float."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def _is_date(value: str) -> bool:
    """Check if string represents a date."""
    return _parse_date(value) is not None


def detect_types(rows: list[dict], columns: list[str]) -> dict:
    """Detect the type of each column.

    For each column, sample up to 100 non-empty values and attempt conversion
    to int, float, or date. If >=80% succeed for a type, label the column as that
    type (int takes precedence over float, float over date, date over text).

    Returns dict mapping column name to 'int', 'float', 'date', or 'text'.
    """
    types = {}
    for col in columns:
        # Collect non-empty values, up to sample size
        values = []
        for row in rows:
            v = row.get(col, "").strip()
            if v:
                values.append(v)
                if len(values) >= 100:
                    break

        if not values:
            types[col] = "text"
            continue

        int_count = sum(1 for v in values if _is_int(v))
        float_count = sum(1 for v in values if _is_float(v))
        date_count = sum(1 for v in values if _is_date(v))

        threshold = 0.8 * len(values)

        # int is a subset of float, so prioritize int then float
        if int_count >= threshold:
            types[col] = "int"
        elif float_count >= threshold:
            types[col] = "float"
        elif date_count >= threshold:
            types[col] = "date"
        else:
            types[col] = "text"

    return types


def compute_numeric_stats(values: list[str]) -> dict | None:
    """Compute summary statistics for a list of numeric string values.

    Returns dict with keys: count, missing, mean, median, min, max, stdev
    or None if no valid numeric values.
    """
    nums = []
    missing = 0
    for v in values:
        if v.strip() == "":
            missing += 1
            continue
        try:
            nums.append(float(v))
        except (ValueError, TypeError):
            pass  # non-numeric in a numeric column; skip

    if not nums:
        return None

    return {
        "count": len(nums),
        "missing": missing,
        "mean": statistics.mean(nums),
        "median": statistics.median(nums),
        "min": min(nums),
        "max": max(nums),
        "stdev": statistics.stdev(nums) if len(nums) >= 2 else 0.0,
    }


def top_frequencies(values: list[str], n: int = 5) -> list[tuple[str, int]]:
    """Return the top-N most frequent non-empty values."""
    counter = Counter(v for v in values if v.strip() != "")
    return counter.most_common(n)


def analyze(rows: list[dict]) -> dict:
    """Run full analysis on a list of row dicts.

    Returns a dict with keys:
        columns: list of column names
        types: dict column->type
        stats: dict column->numeric_stats (or None)
        frequencies: dict column->top_5 list
        missing: dict column->missing_count
    """
    if not rows:
        return {
            "columns": [],
            "types": {},
            "stats": {},
            "frequencies": {},
            "missing": {},
        }

    columns = list(rows[0].keys())
    types = detect_types(rows, columns)

    stats = {}
    frequencies = {}
    missing = {}

    for col in columns:
        all_values = [row.get(col, "") for row in rows]
        missing[col] = sum(1 for v in all_values if v.strip() == "")

        if types[col] in ("int", "float"):
            stats[col] = compute_numeric_stats(all_values)
        else:
            stats[col] = None

        frequencies[col] = top_frequencies(all_values)

    return {
        "columns": columns,
        "types": types,
        "stats": stats,
        "frequencies": frequencies,
        "missing": missing,
    }
