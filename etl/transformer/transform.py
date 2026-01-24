import pandas as pd
import os
import re

# ────────────────────────────────────────────────────────────────
# Папки проекта
# ────────────────────────────────────────────────────────────────

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
CLEAN_DIR = os.path.join(BASE_DIR, "data", "processed")

os.makedirs(CLEAN_DIR, exist_ok=True)

# ────────────────────────────────────────────────────────────────
# Справочники
# ────────────────────────────────────────────────────────────────

KNOWN_BRANDS = [
    "простоквашино",
    "окское",
    "брест-литовск",
    "олейна",
    "greenfield",
    "коломенский",
    "мистраль",
    "петелинка"
]

# ────────────────────────────────────────────────────────────────
# Утилиты
# ────────────────────────────────────────────────────────────────

def parse_price(value):
    if pd.isna(value) or str(value).strip() == "":
        return None
    value = (
        str(value)
        .replace("₽", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    try:
        return float(value)
    except ValueError:
        return None


def extract_weight_from_text(text):
    if pd.isna(text):
        return None, None

    text = str(text).lower().replace(" ", "").replace(",", ".")

    match = re.search(r"(\d+(\.\d+)?)\s*(кг|г|гр|мл|л)", text)
    if not match:
        return None, None

    qty = float(match.group(1))
    unit = match.group(3)

    if unit in ("г", "гр"):
        return int(qty), "g"
    if unit == "кг":
        return int(qty * 1000), "g"
    if unit == "мл":
        return int(qty), "ml"
    if unit == "л":
        return int(qty * 1000), "ml"

    return None, None


def normalize_unit(unit_raw):
    if pd.isna(unit_raw):
        return None, None
    return extract_weight_from_text(unit_raw)

# ────────────────────────────────────────────────────────────────
# Бренд
# ────────────────────────────────────────────────────────────────

def extract_brand(name):
    if pd.isna(name) or str(name).strip() == "":
        return "нет бренда"

    text = str(name).lower()

    for brand in KNOWN_BRANDS:
        pattern = rf"(?:^|[\s,]){re.escape(brand)}(?:[\s,]|$)"
        if re.search(pattern, text):
            return brand

    return "нет бренда"

# ────────────────────────────────────────────────────────────────
# Название товара
# ────────────────────────────────────────────────────────────────

def clean_product_name(name):
    if pd.isna(name):
        return None

    text = str(name).lower()

    # Жесткая унификация
    if "яйц" in text:
        return "яйцо куриное"
    if "молок" in text:
        return "молоко"
    if "чай" in text:
        return "чай"
    if "масло сливоч" in text:
        return "масло сливочное"
    if "масло подсолнеч" in text:
        return "масло подсолнечное"
    if "батон" in text:
        return "батон"

    # Удаляем вес
    text = re.sub(r"\d+(\.\d+)?\s*(кг|г|гр|мл|л|шт)", " ", text)
    text = re.sub(r"\d+(\.\d+)?%", " ", text)

    # Удаляем бренды
    for brand in KNOWN_BRANDS:
        text = re.sub(
            rf"(?:^|[\s,]){re.escape(brand)}(?:[\s,]|$)",
            " ",
            text
        )

    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text or None

# ────────────────────────────────────────────────────────────────
# Логика единиц
# ────────────────────────────────────────────────────────────────

def fix_logical_units(row):
    product = row["product_clean"]
    unit_qty, unit_unit = row["quantity"], row["unit_normalized"]
    prod_qty, _ = extract_weight_from_text(row["product"])

    if product == "чай":
        return (prod_qty, "g") if prod_qty else (None, None)

    if product == "молоко":
        return (prod_qty, "ml") if prod_qty else (unit_qty, "ml")

    if product == "яйцо куриное":
        return unit_qty or 10, "pcs"

    return unit_qty, unit_unit

# ────────────────────────────────────────────────────────────────
# Очистка файла
# ────────────────────────────────────────────────────────────────

def clean_file(path):
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower()

    if "found_name" in df.columns:
        df = df.drop(columns=["found_name"])

    df["price"] = df["price"].apply(parse_price)
    df["price"] = df["price"].apply(
        lambda x: "нет цены" if pd.isna(x) else x
    )

    parsed = df["unit"].apply(normalize_unit)
    df["quantity"] = parsed.apply(lambda x: x[0])
    df["unit_normalized"] = parsed.apply(lambda x: x[1])

    df["brand"] = df["product"].apply(extract_brand)
    df["product_clean"] = df["product"].apply(clean_product_name)

    fixed = df.apply(fix_logical_units, axis=1, result_type="expand")
    df["quantity"] = fixed[0]
    df["unit_normalized"] = fixed[1]

    df = df.drop(columns=["unit"], errors="ignore")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    return df[df["product_clean"].notna()]

# ────────────────────────────────────────────────────────────────
# Основной пайплайн
# ────────────────────────────────────────────────────────────────

def transform_all():
    frames = []

    for file in os.listdir(RAW_DIR):
        if file.endswith(".csv"):
            try:
                df = clean_file(os.path.join(RAW_DIR, file))
                frames.append(df)
                print(f"[OK] cleaned {file}")
            except Exception as e:
                print(f"[ERROR] {file} → {e}")

    if not frames:
        print("Нет данных")
        return

    full_df = pd.concat(frames, ignore_index=True)

    full_df = full_df[
        ["store", "product_clean", "brand", "price",
         "quantity", "unit_normalized", "date"]
    ]

    output_path = os.path.join(CLEAN_DIR, "clean_prices.csv")
    full_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print("\nSaved:", output_path)

# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    transform_all()
