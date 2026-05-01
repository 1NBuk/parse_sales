import re
import psycopg2
from rapidfuzz import fuzz

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
# ЭТАЛОННЫЕ ГРУППЫ
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
# ОЧИСТКА НАЗВАНИЯ
# =========================
def clean_text(name: str) -> str:
    if not name:
        return None

    name = name.lower()

    # убираем мусор
    name = re.sub(r'[^a-zа-я0-9\s]', ' ', name)

    # нормализуем пробелы
    name = re.sub(r'\s+', ' ', name).strip()

    return name if name else None


# =========================
# НОРМАЛЬНЫЙ KEY (ВАЖНО)
# =========================
def make_group_key(name: str) -> str:
    if not name:
        return None

    name = clean_text(name)
    if not name:
        return None

    words = name.split()

    # мусорные слова
    stopwords = {
        "на", "посадку", "кг", "г", "мл", "шт",
        "охлажденное", "охлажденная",
        "клубни", "семена"
    }

    words = [w for w in words if w not in stopwords]

    # сортируем — убираем проблему порядка слов
    words = sorted(words)

    return " ".join(words)


def fuzzy_match_group(name: str, threshold=75):
    best_group = None
    best_score = 0

    for group_id, ref_name in REFERENCE_PRODUCTS.items():

        score = fuzz.token_set_ratio(name, ref_name)

        if score > best_score:
            best_score = score
            best_group = group_id

    if best_score >= threshold:
        return best_group

    return None
# =========================
# МАТЧ ГРУППЫ
# =========================
def match_group(name: str):
    if not name:
        return None

    for group_id, ref_name in REFERENCE_PRODUCTS.items():
        ref_words = set(ref_name.split())
        name_words = set(name.split())

        # мягкое пересечение (а не "in string")
        if len(ref_words & name_words) > 0:
            return group_id

    return None


# =========================
# BUILD PRODUCT GROUPS
# =========================
def build_product_groups(conn):
    cur = conn.cursor()

    # пересоздаём таблицу
    cur.execute("DROP TABLE IF EXISTS product_groups")

    cur.execute("""
        CREATE TABLE product_groups (
            product_id BIGINT PRIMARY KEY,
            product_name TEXT,
            canonical_name TEXT,
            group_id INTEGER,
            group_name TEXT
        )
    """)

    cur.execute("SELECT id, name FROM products")
    rows = cur.fetchall()

    data = []

    for pid, name in rows:

        canonical = make_group_key(name)

        if not canonical:
            continue

        group_id = match_group(canonical)

        # 1. rule-based
        if group_id is not None:
            group_name = REFERENCE_PRODUCTS[group_id]

        # 2. fuzzy fallback
        if group_id is None:
            group_id = fuzzy_match_group(canonical)

            if group_id is not None:
                group_name = REFERENCE_PRODUCTS[group_id]

        # 3. final fallback
        if group_id is None:
            group_id = 0
            group_name = "unknown"
        data.append((
            pid,
            name,
            canonical,
            group_id,
            group_name
        ))

    cur.executemany("""
        INSERT INTO product_groups 
        (product_id, product_name, canonical_name, group_id, group_name)
        VALUES (%s, %s, %s, %s, %s)
    """, data)

    conn.commit()

    print(f"✅ product_groups rebuilt: {len(data)} rows")


# =========================
# VIEW
# =========================
def create_view(conn):
    cur = conn.cursor()

    cur.execute("""
        CREATE OR REPLACE VIEW products_with_groups AS
        SELECT 
            p.id as product_id,
            p.name as product_name,
            pg.canonical_name,
            pg.group_id,
            pg.group_name
        FROM products p
        LEFT JOIN product_groups pg 
            ON p.id = pg.product_id
    """)

    conn.commit()


# =========================
# ANALYSIS
# =========================
def analyze(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT group_name, COUNT(*)
        FROM products_with_groups
        GROUP BY group_name
        ORDER BY COUNT(*) DESC
    """)

    print("\n📊 GROUP DISTRIBUTION:")
    for row in cur.fetchall():
        print(row)


# =========================
# MAIN
# =========================
def main():
    conn = psycopg2.connect(**DB_CONFIG)

    build_product_groups(conn)
    create_view(conn)
    analyze(conn)

    conn.close()

    print("\n🚀 DONE")


if __name__ == "__main__":
    main()