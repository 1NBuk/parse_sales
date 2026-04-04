import psycopg2
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

PG_HOST = os.getenv("PG_HOST")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_DATABASE = "prices_db"
PG_USER = "postgres"

def get_latest_external_factors(n=30):
    conn = psycopg2.connect(
        host=PG_HOST,
        database=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )
    df = pd.read_sql(f"SELECT * FROM external_factors ORDER BY date DESC LIMIT {n}", conn)
    conn.close()
    return df

if __name__ == "__main__":
    df = get_latest_external_factors()
    print(df.to_json(orient="records", date_format="iso"))