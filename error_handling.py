"""
error_handling.py

Reusable tools that make the pipeline reliable:
  1. Logging setup    -> consistent, timestamped messages instead of print()
  2. PipelineError    -> a custom exception for pipeline-specific failures
  3. fetch_with_retry -> an HTTP GET helper that retries on temporary failures

Keeping this logic in its own module follows "Separation of Concerns":
pipeline.py handles ETL, this file handles reliability.
"""

import time
import logging
import requests

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
# basicConfig configures the root logger once for the whole program.
#   level=INFO -> show INFO, WARNING, ERROR and CRITICAL messages
#                 (DEBUG messages are hidden)
#   format     -> every line shows: time | severity level | message
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# A named logger for this project. Other files import this object and call
# logger.info(...), logger.warning(...), logger.error(...) on it.
logger = logging.getLogger("weather_pipeline")


class PipelineError(Exception):
    """
    Custom exception for failures that belong to our pipeline
    (for example: the API kept failing, or returned an unexpected format).

    Why create our own exception class?
    It lets us tell "a known pipeline problem" apart from random Python
    errors (like a typo causing a NameError) when we debug or handle errors.
    """
    pass


def fetch_with_retry(url, params, retries=3, wait=5, timeout=30):
    """
    Send an HTTP GET request and retry if it fails.

    Many API failures are temporary (network glitch, busy server), so trying
    again after a short pause often succeeds.

    Parameters
    ----------
    url     : the API endpoint address
    params  : dictionary of query parameters sent with the request
    retries : maximum number of attempts (default 3)
    wait    : base waiting time in seconds between attempts. The real wait
              grows with each attempt (wait * attempt number). This idea is
              called "backoff" and avoids hammering a struggling server.
    timeout : maximum seconds to wait for the server to answer before
              giving up on that single attempt

    Returns
    -------
    The response body parsed as a Python dictionary (from JSON).

    Raises
    ------
    PipelineError if all attempts fail.
    """
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)

            # raise_for_status() turns HTTP error codes (404, 500, ...)
            # into Python exceptions, so they do not pass silently.
            response.raise_for_status()

            # If we reach this line, the request succeeded.
            # .json() converts the response text into a dictionary.
            return response.json()

        except (requests.RequestException, ValueError) as e:
            # RequestException covers network errors, timeouts and bad HTTP
            # status codes. ValueError covers invalid JSON in the response.
            logger.warning("Attempt %d/%d failed: %s", attempt, retries, e)

            # Only wait if another attempt is still coming.
            if attempt < retries:
                sleep_time = wait * attempt   # backoff: 5s, 10s, 15s, ...
                logger.info("Waiting %d seconds before retry...", sleep_time)
                time.sleep(sleep_time)

    # The loop ended without a successful return, so every attempt failed.
    # "Fail loudly": raise an error instead of continuing with missing data.
    raise PipelineError(f"API failed after {retries} attempts")