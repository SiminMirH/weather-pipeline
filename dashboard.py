"""
dashboard.py

An interactive web dashboard built with Streamlit.
It reads the weather history from the SQLite database (weather.db)
and shows:
  1. KPI cards  -> latest value per city, with change vs the previous run
  2. Line chart -> how a chosen metric changes over time
  3. Summary    -> min / average / max per city
  4. Raw data   -> the full table, for transparency

Run it with:  streamlit run dashboard.py
"""

import os
import sqlite3

import pandas as pd
import streamlit as st

DB_NAME = "weather.db"

# Metrics the user can choose: column name -> label with unit.
# A dictionary keeps the labels in one place and easy to extend.
METRICS = {
    "temperature_c": "Temperature (°C)",
    "humidity_pct": "Humidity (%)",
    "wind_kmh": "Wind speed (km/h)",
}

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
# This must be the first Streamlit command in the script.
st.set_page_config(
    page_title="Weather Pipeline Dashboard",
    page_icon="🌤️",
    layout="wide",   # use the full browser width
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
# @st.cache_data stores the result in memory, so the database is not re-read
# on every click. ttl=300 means the cache expires after 300 seconds (5 min),
# so new pipeline data appears automatically after a short time.
@st.cache_data(ttl=300)
def load_data():
    """Read the whole weather table and prepare it for analysis."""
    conn = sqlite3.connect(DB_NAME)
    try:
        df = pd.read_sql("SELECT * FROM weather", conn)
    finally:
        # Always close the connection, even if reading failed.
        conn.close()

    # Timestamps are stored as text in the database.
    # Convert them to real datetime objects so charts sort them correctly.
    df["collected_at"] = pd.to_datetime(df["collected_at"], utc=True, format="ISO8601")

    # Sort by time so "latest" and "previous" rows are easy to find.
    return df.sort_values("collected_at").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Guard: make sure the database exists and has data
# ---------------------------------------------------------------------------
# Without this check, a missing file would crash the page with a long,
# confusing error. A friendly message is much better for users.
if not os.path.exists(DB_NAME):
    st.error(f"Database file '{DB_NAME}' was not found. Run pipeline.py first.")
    st.stop()   # stop executing the rest of the script

try:
    data = load_data()
except Exception as e:
    st.error(f"Could not read the database: {e}")
    st.stop()

if data.empty:
    st.warning("The database is empty. Run pipeline.py to collect data.")
    st.stop()

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------
st.title("🌤️ Weather Pipeline Dashboard")
st.caption(
    "Data is collected automatically by a GitHub Actions workflow "
    "(Extract → Transform → Validate → Load)."
)

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
# Widgets placed in st.sidebar appear in the left panel.
st.sidebar.header("Filters")

all_cities = sorted(data["city"].unique())

# multiselect returns the list of cities the user ticked.
selected_cities = st.sidebar.multiselect(
    "Cities", options=all_cities, default=all_cities
)

# selectbox returns ONE choice. format_func shows the nice label
# instead of the raw column name.
metric = st.sidebar.selectbox(
    "Metric for the chart",
    options=list(METRICS.keys()),
    format_func=lambda key: METRICS[key],
)

# If the user unticks every city there is nothing to show.
if not selected_cities:
    st.info("Select at least one city in the sidebar.")
    st.stop()

# Keep only the rows of the selected cities.
filtered = data[data["city"].isin(selected_cities)]

# ---------------------------------------------------------------------------
# Section 1: overview numbers
# ---------------------------------------------------------------------------
# nunique() on collected_at = number of distinct pipeline runs.
total_runs = filtered["collected_at"].nunique()
last_run = filtered["collected_at"].max()

col1, col2, col3 = st.columns(3)
col1.metric("Total rows", len(filtered))
col2.metric("Pipeline runs", total_runs)
col3.metric("Last update (UTC)", last_run.strftime("%Y-%m-%d %H:%M"))

st.divider()

# ---------------------------------------------------------------------------
# Section 2: KPI cards (latest value per city)
# ---------------------------------------------------------------------------
st.subheader("Latest measurements")

# One column per selected city, side by side.
columns = st.columns(len(selected_cities))

for col, city in zip(columns, selected_cities):
    city_df = filtered[filtered["city"] == city]
    latest = city_df.iloc[-1]   # last row = most recent run

    # Change compared with the previous run (needs at least 2 rows).
    # st.metric shows an up/down arrow automatically when delta is given.
    if len(city_df) > 1:
        previous = city_df.iloc[-2]
        delta = round(latest["temperature_c"] - previous["temperature_c"], 1)
    else:
        delta = None

    with col:
        st.markdown(f"**{city}**")
        st.metric("Temperature", f"{latest['temperature_c']} °C", delta)
        st.write(
            f"💧 Humidity: {latest['humidity_pct']}%  \n"
            f"💨 Wind: {latest['wind_kmh']} km/h"
        )

st.divider()

# ---------------------------------------------------------------------------
# Section 3: line chart over time
# ---------------------------------------------------------------------------
st.subheader(f"{METRICS[metric]} over time")

# pivot_table reshapes the data: one row per timestamp, one column per city.
# This is the format st.line_chart needs to draw one line per city.
chart_data = filtered.pivot_table(
    index="collected_at", columns="city", values=metric
)

# With only one or two runs a "line" is just a point, so we explain why.
if total_runs < 2:
    st.info("Only one pipeline run so far. Run the pipeline again to see a trend.")

st.line_chart(chart_data)

# ---------------------------------------------------------------------------
# Section 4: summary statistics
# ---------------------------------------------------------------------------
st.subheader("Summary per city")

# groupby + agg computes several statistics at once, like a pivot table in Excel.
summary = (
    filtered.groupby("city")
    .agg(
        runs=("city", "size"),
        temp_min=("temperature_c", "min"),
        temp_avg=("temperature_c", "mean"),
        temp_max=("temperature_c", "max"),
        humidity_avg=("humidity_pct", "mean"),
        wind_avg=("wind_kmh", "mean"),
    )
    .round(1)
)
st.dataframe(summary, use_container_width=True)

# ---------------------------------------------------------------------------
# Section 5: raw data
# ---------------------------------------------------------------------------
# An expander hides the big table until the user clicks it.
with st.expander("Show raw data"):
    st.dataframe(filtered.sort_values("collected_at", ascending=False))