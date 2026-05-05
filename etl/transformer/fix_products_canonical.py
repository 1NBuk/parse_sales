import re
import psycopg2
from rapidfuzz import fuzz

DB_CONFIG = {
    "dbname": "prices_db",
    "user": "postgres",
    "password": "12345",
    "host": "localhost",
    "port": 5432
}

# =========================
# КАТЕГОРИИ
# =========================
REFERENCE_PRODUCTS = {
    1: "яйцо куриное",
    9: "курица",
    2: "батон",
    3: "молоко",
    4: "сахар",
    5: "соль",
    6: "гречка",
    7: "масло подсолнечное",
    8: "масло сливочное",
    10: "чай",
    11: "картофель",
    12: "лук",
    13: "морковь",
    14: "капуста",
    15: "яблоки",
    17: "хлеб",
    18: "сок",
    19: "крупа",
    20: "семена"   # 🌱 теперь сюда же и сок по твоему требованию
}

# =========================
# CLEAN
# =========================
def clean_text(text: str):
    if not text:
        return None
    text = text.lower()
    text = re.sub(r'[^a-zа-я0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text or None


# =========================
# 🌱 СЕМЕНА + САЖЕНЦЫ + РАССАДА
# =========================
def is_seed(text: str) -> bool:
    return any(x in text for x in [
        "семен",
        "сажен",
        "рассада"
    ])


# =========================
# 🍹 СОК (в ту же категорию 20)
# =========================
def is_juice(text: str) -> bool:
    return "сок" in text


# =========================
# 🔥 HARD RULES (ПРИОРИТЕТНЫЕ)
# =========================
def hard_rules(text: str):

    # 🌱 ВСЁ РАСТИТЕЛЬНОЕ (и СОК ТУДА ЖЕ как ты попросил)
    if is_seed(text) or is_juice(text):
        return 20

    # 🥚 яйца
    if "яйцо" in text:
        return 1

    # 🐔 курица / мясо
    if any(x in text for x in ["куриц", "цыпл", "филе", "бедро", "грудк", "шницель"]):
        return 9

    # 🧈 масло
    if "масло" in text:
        if "сливоч" in text:
            return 8
        return 7

    # 🍬 сахар
    if "сахар" in text:
        return 4

    return None


# =========================
# KEYWORDS (добивка unknown)
# =========================
KEYWORDS = {
    20: ["семен", "сажен", "рассада", "сок", "фреш"],
    10: ["чай", "greenfield", "ceylon"],
    15: ["яблок", "гала", "golden", "яблон"],
    6: ["греч", "ядрица"],
    3: ["молок"],
    4: ["сахар", "cахар кусковой"],
    5: ["соль"],
    11: ["карто"],
    12: ["лук"],
    13: ["морк"],
    14: ["капуст"],
    17: ["хлеб", "батон"],
    19: ["круп", "перлов", "пшено"]
}


def keyword_match(text: str):
    for gid, words in KEYWORDS.items():
        if any(w in text for w in words):
            return gid
    return None


# =========================
# FUZZY (последний шанс)
# =========================
def fuzzy_match(text: str, threshold=72):
    best_id = None
    best_score = 0

    for gid, ref in REFERENCE_PRODUCTS.items():
        score = fuzz.token_set_ratio(text, ref)
        if score > best_score:
            best_score = score
            best_id = gid

    return best_id if best_score >= threshold else None


# =========================
# MATCH PIPELINE
# =========================
def match_group(text: str):

    if not text:
        return None

    r = hard_rules(text)
    if r is not None:
        return r

    r = keyword_match(text)
    if r is not None:
        return r

    return fuzzy_match(text)


# =========================
# BUILD TABLE
# =========================
def build(conn):
    cur = conn.cursor()

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
        norm = clean_text(name)
        if not norm:
            continue

        gid = match_group(norm)

        if gid is None:
            gid = 0
            gname = "unknown"
        else:
            gname = REFERENCE_PRODUCTS[gid]

        data.append((pid, name, norm, gid, gname))

    cur.executemany("""
        INSERT INTO product_groups
        VALUES (%s,%s,%s,%s,%s)
    """, data)

    conn.commit()
    print(f"✅ DONE: {len(data)} rows")


# =========================
# MAIN
# =========================
def main():
    conn = psycopg2.connect(**DB_CONFIG)
    build(conn)
    conn.close()

if __name__ == "__main__":
    main()