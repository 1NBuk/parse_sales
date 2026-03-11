import os
import csv
import psycopg2
from datetime import datetime

# --------------------------------------------------
# Настройки PostgreSQL
# --------------------------------------------------
PG_HOST = "localhost"
PG_DATABASE = "prices_db"
PG_USER = "postgres"
PG_PASSWORD = "12345"
PG_TABLE = "prices"

# --------------------------------------------------
# Логирование
# --------------------------------------------------
def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{timestamp}] {message}"
    print(text)

# --------------------------------------------------
# Преобразование пустых значений
# --------------------------------------------------
def null_if_empty(value):
    if value == "" or value is None:
        return None
    return value

# --------------------------------------------------
# Функция загрузки CSV в PostgreSQL
# --------------------------------------------------
def upload(csv_file):

    if not os.path.exists(csv_file):
        log(f"Файл не найден: {csv_file}")
        return

    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            database=PG_DATABASE,
            user=PG_USER,
            password=PG_PASSWORD
        )

        cur = conn.cursor()

        with open(csv_file, "r", encoding="utf-8-sig") as f:

            reader = csv.DictReader(f)

            for row in reader:

                cur.execute(
                    f"""
                    INSERT INTO {PG_TABLE}
                    (store, product_clean, brand, price, quantity, unit_normalized, date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        null_if_empty(row["store"]),
                        null_if_empty(row["product_clean"]),
                        null_if_empty(row["brand"]),
                        null_if_empty(row["price"]),
                        null_if_empty(row["quantity"]),
                        null_if_empty(row["unit_normalized"]),
                        null_if_empty(row["date"])
                    )
                )

        conn.commit()
        cur.close()
        conn.close()

        log(f"Данные из {os.path.basename(csv_file)} загружены в PostgreSQL")

    except Exception as e:
        log(f"Ошибка загрузки в PostgreSQL: {e}")


# --------------------------------------------------
# Можно запускать отдельно
# --------------------------------------------------
if __name__ == "__main__":

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

    for file_name in os.listdir(PROCESSED_DIR):
        if file_name.endswith(".csv"):
            upload(os.path.join(PROCESSED_DIR, file_name))