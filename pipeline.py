"""
pipeline.py

A simple ETL (Extract, Transform, Load) pipeline:
  Extract   -> fetch current weather for several cities from the Open-Meteo API
  Transform -> clean the raw data and shape it into a table
  Validate  -> run data quality checks (stop if the data is bad)
  Load      -> append the table to a local SQLite database

Run it with:  python pipeline.py
"""

import sys
import sqlite3
import pandas as pd
from datetime import datetime, timezone

# Import our reusable helpers from the separate modules.
from error_handling import logger, fetch_with_retry, PipelineError
from data_quality import validate

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
# Cities to collect data for: name -> (latitude, longitude).
# To track another city, just add one line here.
CITIES = {
    "Munich": (48.14, 11.58),
    "Tehran": (35.69, 51.39),
    "Berlin": (52.52, 13.41),
}

# Free weather API, no API key required.
API_URL = "https://api.open-meteo.com/v1/forecast"

# SQLite stores the whole database in this single file.
DB_NAME = "weather.db"


def extract():
    """
    E (Extract): download the current weather of every city from the API.

    Returns a list of dictionaries, one dictionary per city.
    """
    rows = []

    # Loop over every city and request its weather separately.
    for city, (lat, lon) in CITIES.items():
        # Query parameters sent to the API:
        # "current" lists the weather variables we want to receive.
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        }

        # Use our retry helper instead of calling requests.get directly,
        # so temporary network problems do not break the whole run.
        payload = fetch_with_retry(API_URL, params)

        # Defensive check: make sure the response has the structure we expect.
        # If the API changes its format, we want a clear error right here
        # and not a confusing one later.
        if "current" not in payload:
            raise PipelineError(f"Unexpected API response for {city}: {payload}")

        # Take only the "current" part of the response and add the city name,
        # because the API response itself does not tell us which city it was.
        data = payload["current"]
        data["city"] = city
        rows.append(data)

        logger.info("Fetched data for %s", city)

    return rows


def transform(rows):
    """
    T (Transform): convert raw API data into a clean, well-named table.

    Steps: build DataFrame -> rename columns -> add timestamp ->
           keep only the needed columns.

    Note: we do NOT drop incomplete rows here. Missing values are detected
    and reported by data_quality.validate(), so problems are never hidden.
    """
    # A DataFrame is a table (rows and columns) in pandas.
    df = pd.DataFrame(rows)

    # Rename the API's technical column names into clear names with units.
    df = df.rename(columns={
        "temperature_2m": "temperature_c",       # degrees Celsius
        "relative_humidity_2m": "humidity_pct",  # percent
        "wind_speed_10m": "wind_kmh",            # kilometers per hour
    })

    # Record WHEN we collected the data, in UTC (a universal time zone).
    # isoformat() gives a standard text format like 2026-11-02T09:29:59+00:00.
    # Without a timestamp we could not build a history over time.
    df["collected_at"] = datetime.now(timezone.utc).isoformat()

    # Keep only the columns we need, in a fixed order.
    # This also drops extra API columns such as "time" and "interval".
    df = df[["city", "temperature_c", "humidity_pct", "wind_kmh", "collected_at"]]

    return df


def load(df):
    """
    L (Load): append the clean table to the SQLite database.

    if_exists="append" adds new rows and keeps the old ones,
    so the table grows into a history with every run.
    """
    conn = sqlite3.connect(DB_NAME)   # creates weather.db if it doesn't exist
    try:
        # to_sql writes the DataFrame into a table named "weather".
        # index=False means: do not save the DataFrame's row numbers.
        df.to_sql("weather", conn, if_exists="append", index=False)
    finally:
        # "finally" always runs, even if an error happened above,
        # so the database connection is never left open.
        conn.close()


def main():
    """Run the full pipeline: Extract -> Transform -> Validate -> Load."""
    try:
        rows = extract()
        df = transform(rows)

        # Stop here if the data is bad. If validate() raises an error,
        # load() below is never reached, so bad data is never saved.
        validate(df, CITIES.keys())

        load(df)
        logger.info("%d rows loaded successfully.", len(df))
    except Exception:
        # logger.exception prints the error message AND the full traceback,
        # which makes debugging much easier.
        logger.exception("Pipeline failed")

        # Exit code 1 means "failure". GitHub Actions sees this and marks the
        # workflow run as failed (red), and can notify you by email.
        sys.exit(1)


# This block runs main() only when the file is executed directly
# (python pipeline.py), not when it is imported by another file.
if __name__ == "__main__":
    main()