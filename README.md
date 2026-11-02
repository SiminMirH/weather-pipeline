# 🌤️ Weather Data Pipeline

An automated **ETL pipeline** that collects current weather data for several cities every day, validates it, stores it in a database, and shows it in an interactive dashboard. The whole workflow runs in the cloud with **GitHub Actions**, with no manual work after setup.

I built this project to learn the core ideas of data engineering: pipelines, orchestration, reliability, data quality and dashboards.

---

## Table of Contents

1. [What the project does](#what-the-project-does)
2. [Architecture](#architecture)
3. [Tech stack](#tech-stack)
4. [Project structure](#project-structure)
5. [How each part works](#how-each-part-works)
6. [Getting started (run it locally)](#getting-started-run-it-locally)
7. [Automation with GitHub Actions](#automation-with-github-actions)
8. [Dashboard](#dashboard)
9. [Testing the error handling and data quality](#testing-the-error-handling-and-data-quality)
10. [Design decisions](#design-decisions)
11. [Known limitations](#known-limitations)
12. [Ideas for future improvement](#ideas-for-future-improvement)
13. [Key concepts for beginners](#key-concepts-for-beginners)

---

## What the project does

Every day, the pipeline:

1. **Extracts** the current temperature, humidity and wind speed for Munich, Tehran and Berlin from the free [Open-Meteo API](https://open-meteo.com/) (no API key needed).
2. **Transforms** the raw response into a clean table with clear column names and a UTC timestamp.
3. **Validates** the data (completeness, valid ranges, no duplicates). If anything is wrong, the pipeline stops and **nothing is saved**.
4. **Loads** the clean rows into a **SQLite** database (`weather.db`), so a history builds up over time.
5. A **Streamlit dashboard** reads the database and visualizes the history.

Because it runs on GitHub's servers, it works even when my laptop is turned off.

---

## Architecture

```
                 ┌──────────────────────── GitHub Actions (daily, cloud) ───────────────────────┐
                 │                                                                              │
 Open-Meteo API ─┼─► Extract ─► Transform ─► Validate ─► Load ─► weather.db ─► commit to repo    │
                 │   (retry)    (pandas)    (quality)   (SQLite)                                │
                 └──────────────────────────────────────────────────────────────────────────────┘
                                                                      │
                                                                      ▼
                                                           Streamlit dashboard
```

The pattern **source → clean → validate → store → schedule → report** is the same one companies use for sales, finance or CRM data. Only the scale and the tools change.

---

## Tech stack

| Area | Tool |
|---|---|
| Language | Python 3.13 |
| Data handling | pandas |
| HTTP requests | requests |
| Database | SQLite |
| Dashboard | Streamlit |
| Automation / scheduling | GitHub Actions (cron) |
| Version control | Git and GitHub |

---

## Project structure

```
weather-pipeline/
├── .github/
│   └── workflows/
│       └── daily.yml        # GitHub Actions workflow (schedule + steps)
├── pipeline.py              # Main ETL logic (Extract, Transform, Validate, Load)
├── error_handling.py        # Logging, custom exception, retry with backoff
├── data_quality.py          # Data quality checks that run before loading
├── check.py                 # Small helper to inspect the database
├── dashboard.py             # Streamlit dashboard
├── requirements.txt         # Python dependencies
├── weather.db               # SQLite database (updated automatically)
├── .gitignore
└── README.md
```

---

## How each part works

### `pipeline.py` (the ETL)

| Step | Function | What it does |
|---|---|---|
| **E**xtract | `extract()` | Calls the API once per city and collects the `current` weather block. Uses `fetch_with_retry` so temporary network problems do not break the run. |
| **T**ransform | `transform()` | Builds a pandas DataFrame, renames technical columns (`temperature_2m` → `temperature_c`), adds a UTC `collected_at` timestamp and keeps only the needed columns. |
| Validate | `validate()` | Runs the quality checks. Raises an error if the data is bad. |
| **L**oad | `load()` | Appends the rows to the `weather` table in SQLite. The connection is always closed, even if an error happens. |

`main()` runs these steps in order. If anything fails, it logs the full error and exits with **code 1**, which makes the GitHub Actions run turn **red** (and GitHub can notify me by email).

### `error_handling.py` (reliability)

- **Logging**: timestamped messages with a severity level (`INFO`, `WARNING`, `ERROR`) instead of plain `print`.
- **`PipelineError`**: a custom exception that separates known pipeline failures from random Python bugs.
- **`fetch_with_retry`**: retries a failed API call up to 3 times and waits longer after each failure (5s, 10s, ...). This is called **backoff**, and it avoids hammering a struggling server. If all attempts fail, it **fails loudly** instead of silently continuing with missing data.

### `data_quality.py` (trust in the data)

Checks run between Transform and Load, so bad data never reaches the database.

| Dimension | Meaning | Check in this project |
|---|---|---|
| **Completeness** | Is everything we expected present? | Every configured city exists, no null values |
| **Validity** | Are the values possible? | Temperature −60 to 60 °C, humidity 0 to 100 %, wind 0 to 250 km/h |
| **Uniqueness** | Any unwanted duplicates? | One row per city per run |

All problems are collected and logged **together** (not just the first one), then the pipeline stops if there is at least one.

### `dashboard.py` (reporting)

An interactive Streamlit page with:

- Overview numbers: total rows, number of pipeline runs, last update time
- **KPI cards**: the latest value per city, with the change compared to the previous run
- A **time-series line chart** for a metric of your choice (temperature, humidity or wind)
- A **summary table** (min, average, max per city)
- An expandable **raw data** table
- Sidebar filters for cities and metric
- Friendly messages if the database is missing or empty

---

## Getting started (run it locally)

### Prerequisites

- Python 3.10 or newer
- Git
- (Optional) VS Code

### 1. Clone the repository

```bash
git clone https://github.com/siminMirH/weather-pipeline.git
cd weather-pipeline
```

### 2. Create and activate a virtual environment

A **virtual environment** keeps this project's libraries separate from your other Python projects.

```bash
python -m venv venv
```

Windows (PowerShell):

```bash
venv\Scripts\activate
```

Windows (Command Prompt):

```bash
venv\Scripts\activate.bat
```

Mac / Linux:

```bash
source venv/bin/activate
```

You should see `(venv)` at the start of the terminal line.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the pipeline

```bash
python pipeline.py
```

Expected output (timestamps will differ):

```
... | INFO | Fetched data for Munich
... | INFO | Fetched data for Tehran
... | INFO | Fetched data for Berlin
... | INFO | Data quality checks passed (3 rows).
... | INFO | 3 rows loaded successfully.
```

Each run adds **3 new rows** (one per city) to `weather.db`.

### 5. Inspect the data

```bash
python check.py
```

This prints the whole table, the total number of rows and the number of rows per city.

### 6. Start the dashboard

```bash
streamlit run dashboard.py
```

Open `http://localhost:8501` in your browser. Press `Ctrl + C` in the terminal to stop it.

> The dashboard caches data for 5 minutes. After pulling new data, press `C` in the page and choose **Clear cache** to see it immediately.

---

## Automation with GitHub Actions

The file `.github/workflows/daily.yml` defines the automated workflow.

| Concept | In this project |
|---|---|
| **Trigger** | `schedule` (cron `0 6 * * *`, every day at 06:00 UTC) and `workflow_dispatch` (manual run button) |
| **Environment** | A fresh `ubuntu-latest` virtual machine in GitHub's cloud |
| **Steps** | Check out the code → set up Python → install requirements → run `pipeline.py` → commit the updated `weather.db` back to the repository |
| **Permissions** | `contents: write`, so the workflow is allowed to push the updated database |

### Run it manually

1. Open the repository on GitHub.
2. Go to the **Actions** tab.
3. Select **Daily Weather Pipeline**.
4. Click **Run workflow**.

A green ✅ means success. A red ❌ means a step failed; open it to read the log.

### Good to know

- GitHub may start scheduled runs a few minutes late. This is normal.
- To get the newest data on your own computer, run `git pull`.

---

## Dashboard

Run it locally with `streamlit run dashboard.py`.

**Live demo:** _add your Streamlit Community Cloud link here after deploying_

To deploy for free, use [Streamlit Community Cloud](https://share.streamlit.io): connect the GitHub repository, choose branch `main` and main file `dashboard.py`. Since the workflow updates `weather.db` in the repository every day, the online dashboard shows fresh data automatically.

---

## Testing the error handling and data quality

A pipeline you have not tried to break is a pipeline you cannot trust. Two simple experiments:

**1. Simulate an API failure.** Temporarily change the URL in `pipeline.py`:

```python
API_URL = "https://api.open-meteo.com/v1/forecastXXX"
```

Run the pipeline. You should see 3 failed attempts with waiting time between them, then `Pipeline failed`. Restore the correct URL afterwards.

**2. Simulate bad data.** Temporarily add this line in `main()` right after `df = transform(rows)`:

```python
df.loc[0, "humidity_pct"] = 150   # TEMPORARY TEST, remove afterwards
```

Run the pipeline. You should see a `DATA QUALITY` error and **no new rows** in the database (verify with `python check.py`). Remove the line afterwards.

---

## Design decisions

- **Retry with backoff** for temporary failures, **fail fast** with a non-zero exit code for real failures, so the orchestrator (GitHub Actions) knows the run failed.
- **No silent `dropna()`**. Missing values are detected and reported by the quality checks instead of being quietly removed, because hidden data problems are worse than visible ones.
- **Separation of concerns**: ETL, reliability and data quality each live in their own module, which keeps the code readable and reusable.
- **Append-only loading** builds a time series that can be analyzed later.
- **Validation before loading** guarantees that bad data never enters the database.

---

## Known limitations

This is a learning project, so some choices would be different in production:

- **The database is stored in Git.** This is convenient for learning, but binary files make the repository history grow. Real systems use a proper database or warehouse (PostgreSQL, BigQuery, Snowflake) or object storage (S3).
- **Not idempotent**: running the pipeline twice at the same time inserts two sets of rows. A production version would use a unique key (for example city + hour) and upserts.
- **No alerting beyond GitHub's failure emails.** There is no Slack or email notification built into the code.
- **Quality thresholds are fixed** in code and are simple range checks, not statistical anomaly detection.
- **One shared requirements file** for the pipeline and the dashboard. Larger projects separate them.

---

## Ideas for future improvement

- [ ] Move from SQLite to **PostgreSQL** (for example with Docker)
- [ ] Rewrite the pipeline as an **Apache Airflow** DAG
- [ ] Add **unit tests** with `pytest` and run them in GitHub Actions
- [ ] Add **alerts** to Slack or email on failure
- [ ] Add **upserts** so duplicate runs cannot create duplicate data
- [ ] Add more variables (precipitation, pressure) and more cities
- [ ] Use a tool such as **Great Expectations**, **dbt tests** or **Soda** for data quality

---

## Key concepts for beginners

| Term | Simple meaning |
|---|---|
| **Workflow** | A set of steps done in a fixed order |
| **Automation** | A system runs the workflow for you, without manual clicks |
| **ETL** | Extract (get data), Transform (clean it), Load (store it) |
| **Pipeline** | The automated path data travels from source to destination |
| **Trigger** | What starts a workflow (a schedule, a button, a new file) |
| **Cron** | A compact syntax for schedules, such as `0 6 * * *` = every day at 06:00 |
| **Cloud** | Running code on someone else's servers instead of your own computer |
| **Orchestration** | Scheduling and managing the steps of pipelines (Airflow, Prefect, Dagster) |
| **Retry / Backoff** | Trying again after a failure, waiting longer each time |
| **Data quality** | Checking that data is complete, valid and unique |
| **Virtual environment** | An isolated space for one project's Python libraries |
| **Exit code** | A number a program returns when it ends: `0` = success, non-zero = failure |

---

## Data source

Weather data is provided by [Open-Meteo](https://open-meteo.com/), a free and open weather API.

## License

This project is for educational purposes. Feel free to use it as a starting point for your own learning.
