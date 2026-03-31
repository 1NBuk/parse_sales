import psycopg2
import pandas as pd

PG_HOST = "localhost"
PG_DATABASE = "prices_db"
PG_USER = "postgres"
PG_PASSWORD = "12345"

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