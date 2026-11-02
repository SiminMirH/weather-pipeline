import sqlite3
import pandas as pd

conn = sqlite3.connect("weather.db")
print(pd.read_sql("SELECT * FROM weather", conn))
conn.close()