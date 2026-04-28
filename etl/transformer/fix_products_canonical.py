import re
import psycopg2
import pandas as pd

# =========================
# DB CONFIG
# =========================
DB_CONFIG = {
    "dbname": "prices_db",
    "user": "postgres",
    "password": "12345",
    "host": "localhost",
    "port": 5432
}

# =========================
# ЭТАЛОННЫЕ ТОВАРЫ
# =========================
REFERENCE_PRODUCTS = {
    1: "яйцо куриное",
    2: "батон",
    3: "молоко",
    4: "сахар",
    5: "соль",
    6: "гречка",
    7: "масло подсолнечное",
    8: "масло сливочное",
    9: "курица",
    10: "чай",
    11: "картофель",
    12: "лук",
    13: "морковь",
    14: "капуста",
    15: "яблоки",
    17: "хлеб",
    18: "сок",
    19: "крупа"
}

# =========================
# КЛЮЧЕВЫЕ СЛОВА
# =========================
KEYWORDS = {
    'яйцо': 1, 'яйца': 1,
    'батон': 2,
    'хлеб': 17,
    'молоко': 3,
    'сахар': 4, 'рафинад': 4, 'песок': 4,
    'соль': 5,
    'гречка': 6,
    'крупа': 19,
    'подсолнечное': 7,
    'сливочное': 8,
    'курица': 9, 'филе': 9,
    'чай': 10,
    'картофель': 11,
    'лук': 12,
    'морковь': 13,
    'капуста': 14,
    'яблоки': 15,
    'сок': 18
}
def is_seed_product(name: str) -> bool:
    if not name:
        return False

    name = name.lower()

    seed_keywords = [
        'семена', 'семян', 'семенной',
        'рассада', 'саженец', 'саженцы',
        'посадка', 'на посадку',
        'севок', 'луковицы', 'клубни',
        'агрофирма', 'гавриш', 'аэлита',
        'гибрид', 'f1', 'f2'
    ]

    return any(word in name for word in seed_keywords)

def clean_name(name: str) -> str:
    if not name:
        return 'unknown'

    name = name.lower().strip()

    name = re.sub(r'[^a-zа-я0-9\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()

    return name if name else 'unknown'

def match_to_reference(name: str):
    if not name or name == 'unknown':
        return None

    for keyword, ref_id in sorted(KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True):
        if keyword in name:
            return ref_id

    return None


# =========================
# ОСНОВНАЯ ЛОГИКА
# =========================
def build_product_groups(conn):
    cur = conn.cursor()

    # создаём таблицу если нет
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_groups (
            product_id BIGINT PRIMARY KEY,
            product_name TEXT,
            canonical_name TEXT,
            group_id INTEGER,
            group_name TEXT
        )
    """)

    # читаем продукты
    cur.execute("SELECT id, name FROM products")
    rows = cur.fetchall()

    data = []

    for pid, name in rows:
        if is_seed_product(name):
            continue

        canonical = clean_name(name)

        if canonical == 'unknown':
            continue

        group_id = match_to_reference(canonical)

        if group_id is None:
            continue

        data.append((
            pid,
            name,
            canonical,
            group_id,
            REFERENCE_PRODUCTS[group_id]
        ))

    # 🔥 ВАЖНО: UPSERT (обновление при новых данных)
    cur.executemany("""
        INSERT INTO product_groups 
        (product_id, product_name, canonical_name, group_id, group_name)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (product_id) DO UPDATE
        SET 
            product_name = EXCLUDED.product_name,
            canonical_name = EXCLUDED.canonical_name,
            group_id = EXCLUDED.group_id,
            group_name = EXCLUDED.group_name
    """, data)

    conn.commit()
    print(f"✅ product_groups обновлена: {len(data)} записей")

    # обновляем view
    cur.execute("""
        CREATE OR REPLACE VIEW products_with_groups AS
        SELECT 
            p.id as product_id,
            p.name as product_name,
            pg.canonical_name,
            pg.group_id,
            COALESCE(pg.group_name, 'unknown') as group_name
        FROM products p
        LEFT JOIN product_groups pg ON p.id = pg.product_id
    """)

    conn.commit()


# =========================
# АНАЛИЗ
# =========================
def analyze(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT group_name, COUNT(*)
        FROM products_with_groups
        GROUP BY group_name
        ORDER BY COUNT(*) DESC
    """)

    print("\n📊 Результат:")
    for row in cur.fetchall():
        print(row)


# =========================
# MAIN
# =========================
def main():
    conn = psycopg2.connect(**DB_CONFIG)

    build_product_groups(conn)
    analyze(conn)

    conn.close()
    print("\n🚀 ГОТОВО")


if __name__ == "__main__":
    main()