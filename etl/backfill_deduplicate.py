import pandas as pd
import psycopg2
from datetime import date
from dotenv import load_dotenv
import os

load_dotenv()

PG_HOST = os.getenv("PG_HOST")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_DATABASE = "prices_db"
PG_USER = "postgres"

START_DATE = date(2026, 2, 25)


# --------------------------------------------------
# CONNECTION
# --------------------------------------------------

def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        database=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )


# --------------------------------------------------
# ТВОЯ ФУНКЦИЯ (копируешь сюда)
# --------------------------------------------------

def select_closest_to_previous(df):
    df = df.sort_values("date")
    result_rows = []

    group_cols = ["store", "product_clean", "brand"]

    for keys, group in df.groupby(group_cols):
        group = group.sort_values("date")

        prev_price = None
        prev_qty = None

        for date_val, day_group in group.groupby("date"):

            if len(day_group) == 1:
                chosen = day_group.iloc[0]

            else:
                day_group = day_group.copy()

                if prev_price is not None and prev_qty is not None:
                    day_group["score"] = (
                        (day_group["price"] - prev_price).abs().fillna(1e6) +
                        (day_group["quantity"] - prev_qty).abs().fillna(1e6)
                    )
                else:
                    median_price = day_group["price"].median()
                    day_group["score"] = (
                        (day_group["price"] - median_price).abs().fillna(1e6)
                    )

                chosen = day_group.sort_values("score").iloc[0]

            result_rows.append(chosen)

            prev_price = chosen["price"]
            prev_qty = chosen["quantity"]

    return pd.DataFrame(result_rows)


# --------------------------------------------------
# MAIN BACKFILL
# --------------------------------------------------

def backfill():

    conn = get_connection()

    print("📥 Загружаем данные из БД...")

    df = pd.read_sql(f"""
        SELECT *
        FROM prices_raw
        WHERE date >= '{START_DATE}'
    """, conn)

    print(f"Загружено строк: {len(df)}")

    # защита типов
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

    print("🧠 Применяем дедупликацию...")

    df_clean = select_closest_to_previous(df)

    print(f"После очистки: {len(df_clean)}")

    cur = conn.cursor()

    print("🗑 Удаляем старые данные...")

    cur.execute(f"""
        DELETE FROM prices_history
        WHERE date >= %s
    """, (START_DATE,))

    print("📤 Загружаем новые данные...")

    for _, row in df_clean.iterrows():
        cur.execute("""
            INSERT INTO prices_history
            (product_id, store_id, price, quantity, unit, date)

            SELECT
                pr.id,
                st.id,
                %s,
                %s,
                %s,
                %s

            FROM products pr
            JOIN stores st ON st.name = %s

            WHERE pr.name = %s
        """, (
            row["price"],
            row["quantity"],
            row["unit_normalized"],
            row["date"],
            row["store"],
            row["product_clean"]
        ))

    conn.commit()

    print("✅ Backfill завершён")

    cur.close()
    conn.close()


# --------------------------------------------------

if __name__ == "__main__":
    backfill()