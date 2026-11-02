"""
data_quality.py

Data Quality checks that run BETWEEN Transform and Load.

Idea: bad data should never reach the database. If any check fails,
the pipeline stops and nothing is saved.

Checks implemented:
  1. Completeness -> every expected city is present, no missing values
  2. Validity     -> numbers are inside physically possible ranges
  3. Uniqueness   -> no city appears twice in the same run
"""

from error_handling import logger, PipelineError

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
# Allowed (min, max) range for each numeric column.
# Values outside these ranges are almost certainly API errors or sensor bugs.
# Keeping rules in one dictionary makes them easy to change later.
VALID_RANGES = {
    "temperature_c": (-60, 60),    # degrees Celsius
    "humidity_pct": (0, 100),      # percent
    "wind_kmh": (0, 250),          # kilometers per hour
}

# Columns that must exist in the table.
REQUIRED_COLUMNS = ["city", "temperature_c", "humidity_pct", "wind_kmh", "collected_at"]


def check_columns(df):
    """Structure check: make sure all required columns exist.
    Returns a list of problems (empty list = no problems)."""
    problems = []
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        problems.append(f"Missing columns: {missing}")
    return problems


def check_completeness(df, expected_cities):
    """
    Completeness: did we get data for every city we asked for,
    and are there any empty (null) values?
    """
    problems = []

    # Compare the cities we expected with the cities actually in the table.
    # set() makes the comparison independent of order.
    missing_cities = set(expected_cities) - set(df["city"])
    if missing_cities:
        problems.append(f"Missing cities: {sorted(missing_cities)}")

    # isna().sum().sum() counts all empty cells in the whole table.
    null_count = int(df.isna().sum().sum())
    if null_count > 0:
        problems.append(f"Found {null_count} null values")

    return problems


def check_ranges(df):
    """
    Validity: every numeric value must be inside its allowed range.
    Example: humidity of 150% or temperature of 999 C is impossible.
    """
    problems = []

    for column, (low, high) in VALID_RANGES.items():
        # between() returns True/False per row; "~" flips it,
        # so bad_rows contains only the rows that are OUT of range.
        bad_rows = df[~df[column].between(low, high)]

        for _, row in bad_rows.iterrows():
            problems.append(
                f"{row['city']}: {column}={row[column]} is outside [{low}, {high}]"
            )

    return problems


def check_duplicates(df):
    """
    Uniqueness: one run should produce exactly one row per city.
    Duplicates would double-count that city in later analysis.
    """
    problems = []
    duplicated = df[df.duplicated(subset=["city"], keep=False)]
    if not duplicated.empty:
        problems.append(
            f"Duplicate cities in one run: {sorted(duplicated['city'].unique())}"
        )
    return problems


def validate(df, expected_cities):
    """
    Run all checks. Log every problem found, then raise PipelineError
    if there was at least one, so the bad data is never loaded.
    """
    # Structural check first: if columns are missing, the other checks
    # would crash with confusing KeyError messages, so stop early.
    problems = check_columns(df)
    if problems:
        for p in problems:
            logger.error("DATA QUALITY: %s", p)
        raise PipelineError(f"Data quality failed: {len(problems)} problem(s)")

    # Collect problems from all remaining checks into one list,
    # so we see ALL problems at once, not just the first one.
    problems += check_completeness(df, expected_cities)
    problems += check_ranges(df)
    problems += check_duplicates(df)

    if problems:
        for p in problems:
            logger.error("DATA QUALITY: %s", p)
        raise PipelineError(f"Data quality failed: {len(problems)} problem(s)")

    logger.info("Data quality checks passed (%d rows).", len(df))