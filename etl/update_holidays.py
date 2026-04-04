import psycopg2
from datetime import date
from dotenv import load_dotenv
import os

load_dotenv()

def update_holidays():
    PG_HOST = os.getenv("PG_HOST")
    PG_PASSWORD = os.getenv("PG_PASSWORD")
    PG_DATABASE = "prices_db"
    PG_USER = "postgres"

    # Список праздников
    holidays = [
        # Новый год
        '2023-01-01','2023-01-02','2023-01-03','2023-01-04','2023-01-05','2023-01-06','2023-01-07',
        '2024-01-01','2024-01-02','2024-01-03','2024-01-04','2024-01-05','2024-01-06','2024-01-07',
        '2025-01-01','2025-01-02','2025-01-03','2025-01-04','2025-01-05','2025-01-06','2025-01-07',
        '2026-01-01','2026-01-02','2026-01-03','2026-01-04','2026-01-05','2026-01-06','2026-01-07',
        # остальные праздники
        '2023-02-23','2023-03-08','2023-05-01','2023-05-09','2023-06-12','2023-11-04',
        '2024-02-23','2024-03-08','2024-05-01','2024-05-09','2024-06-12','2024-11-04',
        '2025-02-23','2025-03-08','2025-05-01','2025-05-09','2025-06-12','2025-11-04',
        '2026-02-23','2026-03-08','2026-05-01','2026-05-09','2026-06-12','2026-11-04'
    ]

    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            database=PG_DATABASE,
            user=PG_USER,
            password=PG_PASSWORD
        )
        cur = conn.cursor()

        # Сначала ставим FALSE для всех
        cur.execute("UPDATE calendar SET is_holiday = FALSE;")

        # Затем TRUE для праздников
        cur.execute(
            "UPDATE calendar SET is_holiday = TRUE WHERE date IN %s;",
            (tuple(holidays),)
        )

        conn.commit()
        cur.close()
        conn.close()

        print(f"[{date.today()}] is_holiday обновлён успешно")

    except Exception as e:
        print(f"Ошибка при обновлении is_holiday: {e}")