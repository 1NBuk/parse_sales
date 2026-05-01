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


# --------------------------------------------------
# LOG
# --------------------------------------------------

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


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
# HELPERS
# --------------------------------------------------

def null_if_empty(value):
    if value == "" or value is None:
        return None
    return value


def to_float(value):
    if value == "" or value is None:
        return None
    return float(value)


# --------------------------------------------------
# CSV → RAW (ИСПРАВЛЕНО: очистка перед загрузкой)
# --------------------------------------------------

def upload_csv(csv_file):
    if not os.path.exists(csv_file):
        log(f"Файл не найден: {csv_file}")
        return

    conn = get_connection()
    cur = conn.cursor()

    try:
        # ИСПРАВЛЕНИЕ: Очищаем prices_raw перед новой загрузкой
        log("Очистка таблицы prices_raw...")
        cur.execute(f"TRUNCATE TABLE {RAW_TABLE} CASCADE")
        conn.commit()
        log("Таблица prices_raw очищена")

        inserted_count = 0
        skipped_count = 0

        with open(csv_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Пропускаем строки без важных полей
                if not row.get("product_clean") or not row.get("store"):
                    skipped_count += 1
                    continue

                cur.execute(
                    f"""
                    INSERT INTO {RAW_TABLE}
                    (store, product_clean, brand, price, quantity, unit_normalized, date)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        null_if_empty(row.get("store")),
                        null_if_empty(row.get("product_clean")),
                        null_if_empty(row.get("brand")),
                        to_float(row.get("price")),
                        to_float(row.get("quantity")),
                        null_if_empty(row.get("unit_normalized")),
                        row.get("date")
                    )
                )
                inserted_count += 1

        conn.commit()
        log(f"CSV загружен: {os.path.basename(csv_file)}")
        log(f"  Загружено: {inserted_count} записей")
        log(f"  Пропущено: {skipped_count} записей")

    except Exception as e:
        conn.rollback()
        log(f"Ошибка загрузки CSV: {e}")
        raise

    finally:
        cur.close()
        conn.close()


# --------------------------------------------------
# LOAD STORES
# --------------------------------------------------

def load_stores(cur):
    cur.execute("""
        INSERT INTO stores (name)
        SELECT DISTINCT store
        FROM prices_raw
        WHERE store IS NOT NULL
        ON CONFLICT (name) DO NOTHING;
    """)


# --------------------------------------------------
# LOAD BRANDS
# --------------------------------------------------

def load_brands(cur):
    cur.execute("""
        INSERT INTO brands (name)
        SELECT DISTINCT brand
        FROM prices_raw
        WHERE brand IS NOT NULL
        ON CONFLICT (name) DO NOTHING;
    """)


# --------------------------------------------------
# LOAD PRODUCTS
# --------------------------------------------------

def load_products(cur):
    cur.execute("""
        INSERT INTO products (name, brand_id)
        SELECT DISTINCT
            p.product_clean,
            b.id
        FROM prices_raw p
        LEFT JOIN brands b ON p.brand = b.name
        WHERE p.product_clean IS NOT NULL
        ON CONFLICT (name, brand_id) DO NOTHING;
    """)


# --------------------------------------------------
# LOAD PRICES HISTORY (ИСПРАВЛЕНО)
# --------------------------------------------------

def load_prices_history(cur):
    # ИСПРАВЛЕНИЕ: Удаляем старые записи с такими же датами перед вставкой новых
    log("Удаление старых записей из prices_history для обновляемых дат...")

    cur.execute("""
        DELETE FROM prices_history
        WHERE date IN (SELECT DISTINCT date FROM prices_raw WHERE date IS NOT NULL)
    """)

    deleted_count = cur.rowcount
    log(f"Удалено старых записей: {deleted_count}")

    # Теперь вставляем новые данные
    cur.execute("""
        INSERT INTO prices_history
        (product_id, store_id, price, quantity, unit, date)
        SELECT
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
    """)

    inserted_count = cur.rowcount
    log(f"Вставлено новых записей: {inserted_count}")


# --------------------------------------------------
# LOAD CALENDAR
# --------------------------------------------------

def load_calendar(cur):
    cur.execute("""
        INSERT INTO calendar
        (date, year, month, day, day_of_week, week_of_year, is_weekend)
        SELECT
            date,
            EXTRACT(YEAR FROM date),
            EXTRACT(MONTH FROM date),
            EXTRACT(DAY FROM date),
            EXTRACT(DOW FROM date),
            EXTRACT(WEEK FROM date),
            CASE
                WHEN EXTRACT(DOW FROM date) IN (0,6) THEN TRUE
                ELSE FALSE
            END
        FROM (
            SELECT DISTINCT date
            FROM prices_raw
            WHERE date IS NOT NULL
        ) d
        ON CONFLICT (date) DO NOTHING;
    """)


# --------------------------------------------------
# DISTRIBUTE DATA
# --------------------------------------------------

def distribute_data():
    conn = get_connection()
    cur = conn.cursor()

    try:
        log("Заполнение stores")
        load_stores(cur)

        log("Заполнение brands")
        load_brands(cur)

        log("Заполнение products")
        load_products(cur)

        log("Заполнение calendar")
        load_calendar(cur)

        log("Заполнение prices_history")
        load_prices_history(cur)

        conn.commit()
        log("Данные успешно распределены")

    except Exception as e:
        conn.rollback()
        log(f"Ошибка распределения данных: {e}")
        raise

    finally:
        cur.close()
        conn.close()


def upload(csv_file):
    upload_csv(csv_file)
    distribute_data()


# --------------------------------------------------
# STANDALONE RUN
# --------------------------------------------------

def main():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

    log("Запуск standalone загрузки")

    for file_name in os.listdir(PROCESSED_DIR):
        if file_name.endswith(".csv"):
            csv_path = os.path.join(PROCESSED_DIR, file_name)
            upload(csv_path)

    log("Загрузка завершена")


# --------------------------------------------------

if __name__ == "__main__":
    main()