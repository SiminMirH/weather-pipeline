import requests
import pandas as pd
import sqlite3
from datetime import datetime, timezone

# شهرها و مختصات جغرافیایی آن‌ها (latitude, longitude)
CITIES = {
    "Munich": (48.14, 11.58),
    "Tehran": (35.69, 51.39),
    "Berlin": (52.52, 13.41),
}

DB_NAME = "weather.db"


def extract():
    """E: داده آب‌وهوای فعلی هر شهر را از API می‌گیرد"""
    rows = []
    for city, (lat, lon) in CITIES.items():
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()  # اگر API خطا داد، برنامه متوقف شود
        data = response.json()["current"]
        data["city"] = city
        rows.append(data)
    return rows


def transform(rows):
    """T: داده خام را به یک جدول تمیز تبدیل می‌کند"""
    df = pd.DataFrame(rows)

    df = df.rename(columns={
        "temperature_2m": "temperature_c",
        "relative_humidity_2m": "humidity_pct",
        "wind_speed_10m": "wind_kmh",
    })

    df["collected_at"] = datetime.now(timezone.utc).isoformat()

    df = df[["city", "temperature_c", "humidity_pct", "wind_kmh", "collected_at"]]
    df = df.dropna()  # ردیف‌های ناقص حذف شوند
    return df


def load(df):
    """L: داده را در دیتابیس SQLite ذخیره می‌کند"""
    conn = sqlite3.connect(DB_NAME)
    df.to_sql("weather", conn, if_exists="append", index=False)
    conn.close()


def main():
    rows = extract()
    df = transform(rows)
    load(df)
    print(f"{len(df)} rows loaded.")


if __name__ == "__main__":
    main()