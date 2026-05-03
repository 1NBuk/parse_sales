import os
import csv
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("PG_HOST")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_DATABASE = "prices_db"
PG_USER = "postgres"

RAW_TABLE = "prices_raw"


def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        database=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )


def null_if_empty(value):
    if value == "" or value is None:
        return None
    return value


def to_float(value):
    try:
        return float(value) if value not in ("", None) else None
    except:
        return None


def upload_csv(csv_file):
    if not os.path.exists(csv_file):
        log(f"Файл не найден: {csv_file}")
        return

    conn = get_connection()
    cur = conn.cursor()

    try:
        inserted = 0
        skipped = 0
        seen = set()

        with open(csv_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                store = (row.get("store") or "").strip()
                product = (row.get("product_clean") or "").strip()
                date = (row.get("date") or "").strip()

                if not store or not product:
                    skipped += 1
                    continue

                key = (store, product, date)
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)

                cur.execute(f"""
                    INSERT INTO {RAW_TABLE}
                    (store, product_clean, brand, price, quantity, unit_normalized, date)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                """, (
                    store,
                    product,
                    null_if_empty(row.get("brand")),
                    to_float(row.get("price")),
                    to_float(row.get("quantity")),
                    null_if_empty(row.get("unit_normalized")),
                    date if date else None
                ))

                inserted += 1

        conn.commit()
        log(f"CSV: {os.path.basename(csv_file)} inserted={inserted} skipped={skipped}")

    finally:
        cur.close()
        conn.close()


def load_stores(cur):
    cur.execute("""
        INSERT INTO stores(name)
        SELECT DISTINCT store
        FROM prices_raw
        WHERE store IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)


def load_brands(cur):
    cur.execute("""
        INSERT INTO brands(name)
        SELECT DISTINCT brand
        FROM prices_raw
        WHERE brand IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)


def load_products(cur):
    cur.execute("""
        INSERT INTO products(name, brand_id)
        SELECT DISTINCT p.product_clean, b.id
        FROM prices_raw p
        LEFT JOIN brands b ON p.brand = b.name
        WHERE p.product_clean IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)


def load_prices_history(cur):
    cur.execute("""
        INSERT INTO prices_history
        (product_id, store_id, price, quantity, unit, date)
        SELECT DISTINCT ON (pr.id, st.id, p.date)
            pr.id,
            st.id,
            p.price,
            p.quantity,
            p.unit_normalized,
            p.date
        FROM prices_raw p
        JOIN products pr ON p.product_clean = pr.name
        JOIN stores st ON p.store = st.name
        WHERE p.price IS NOT NULL AND p.date IS NOT NULL
        ORDER BY pr.id, st.id, p.date, p.price DESC
        ON CONFLICT (product_id, store_id, date)
        DO UPDATE SET
            price = EXCLUDED.price,
            quantity = EXCLUDED.quantity,
            unit = EXCLUDED.unit;
    """)


def load_calendar(cur):
    cur.execute("""
        INSERT INTO calendar(date, year, month, day, day_of_week, week_of_year, is_weekend)
        SELECT DISTINCT
            date,
            EXTRACT(YEAR FROM date),
            EXTRACT(MONTH FROM date),
            EXTRACT(DAY FROM date),
            EXTRACT(DOW FROM date),
            EXTRACT(WEEK FROM date),
            EXTRACT(DOW FROM date) IN (0,6)
        FROM prices_raw
        WHERE date IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)


def distribute_data():
    conn = get_connection()
    cur = conn.cursor()

    try:
        load_stores(cur)
        load_brands(cur)
        load_products(cur)
        load_calendar(cur)
        load_prices_history(cur)

        conn.commit()
        log("DISTRIBUTE DONE")

    finally:
        cur.close()
        conn.close()


def upload(file_path):
    upload_csv(file_path)
    distribute_data()


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = os.path.join(base, "data", "processed")

    log("START")

    for f in os.listdir(folder):
        if f.endswith(".csv"):
            upload(os.path.join(folder, f))

    log("FINISH")


if __name__ == "__main__":
    main()