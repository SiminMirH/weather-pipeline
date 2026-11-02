"""
check.py

A small helper script to inspect the database.
It reads the whole "weather" table with SQL and prints it,
plus a short summary, so you can verify the pipeline is working.

Run it with:  python check.py
"""

import sqlite3
import pandas as pd

DB_NAME = "weather.db"

# Connect to the SQLite database file.
conn = sqlite3.connect(DB_NAME)

try:
    # Read every row of the table into a pandas DataFrame using SQL.
    df = pd.read_sql("SELECT * FROM weather", conn)

    # Show the full table.
    print(df)

    # Short summary: total rows and how many rows each city has.
    # Each pipeline run adds one row per city, so the counts should match
    # the number of successful runs.
    print(f"\nTotal rows: {len(df)}")
    print(df.groupby("city").size().rename("rows_per_city"))
finally:
    # Always close the connection, even if an error happened above.
    conn.close()