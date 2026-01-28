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
os.makedirs(RAW_DIR, exist_ok=True)

# ────────────────────────────────────────────────────────────────
# Справочники
# ────────────────────────────────────────────────────────────────

KNOWN_BRANDS = [
    "простоквашино", "окское", "брест-литовск", "олейна",
    "greenfield", "коломенский", "мистраль", "петелинка"
]

FRUITS_VEG = ["картофель", "лук репчатый", "морковь", "капуста белокочанная", "яблоки"]

# ────────────────────────────────────────────────────────────────
# Утилиты
# ────────────────────────────────────────────────────────────────

def remove_invisible_chars(text):
    if pd.isna(text):
        return None
    text = re.sub(r"[\u200B-\u200D\u2060\uFEFF]", "", str(text))
    return text.strip()

def parse_price(value):
    if pd.isna(value) or str(value).strip() == "":
        return None
    value = str(value).replace("₽", "").replace(" ", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None

def extract_weight_from_text(text):
    if pd.isna(text):
        return None, None
    text = str(text).lower().replace(" ", "").replace(",", ".")
    match = re.search(r"(\d+(\.\d+)?)(кг|г|гр|мл|л|шт)?", text)
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
    if unit == "шт":
        return int(qty), "pcs"
    return None, None

def normalize_unit(unit_raw):
    return extract_weight_from_text(unit_raw)

def extract_brand(name):
    if pd.isna(name) or str(name).strip() == "":
        return "No Brand"
    text = str(name).lower()
    if "вкусвилл" in text:
        return "ВкусВилл"
    if "лента" in text:
        return "Лента"
    for brand in KNOWN_BRANDS:
        if re.search(rf"(?:^|[\s,]){re.escape(brand)}(?:[\s,]|$)", text):
            return brand.title()
    return "No Brand"

def clean_product_name(name):
    if pd.isna(name):
        return None
    text = remove_invisible_chars(str(name).lower())
    text = re.sub(r"вкусвилл.*товарный\s+знак.*", "вкусвилл", text, flags=re.DOTALL)
    text = re.sub(r"лента.*товарный\s+знак.*", "лента", text, flags=re.DOTALL)
    # Канонизация популярных товаров
    if "яйц" in text:
        return "Яйцо куриное"
    if "молок" in text:
        return "Молоко"
    if "чай" in text:
        return "Чай"
    if "масло сливоч" in text:
        return "Масло сливочное"
    if "масло подсолнеч" in text:
        return "Масло подсолнечное"
    if "батон" in text:
        return "Батон"
    if "яблок" in text:
        return "Яблоки"
    # Очистка лишнего
    text = re.sub(r"(социальный\s+товар|вес|отечественная|сезонные?)", " ", text)
    text = re.sub(r"\d+(\.\d+)?\s*(кг|г|гр|мл|л|шт)?", " ", text)
    text = re.sub(r"\d+(\.\d+)?%", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.title() if text else None

def fix_logical_units(row):
    product = str(row.get("product_clean", "")).lower()
    qty, unit = row.get("quantity"), row.get("unit_normalized")
    prod_qty, _ = extract_weight_from_text(row.get("product"))
    if product == "чай":
        return (prod_qty or 50, "g")
    if product == "молоко":
        return (prod_qty or 930, "ml")
    if product == "яйцо куриное":
        return (10, "pcs")
    if product in [x.lower() for x in FRUITS_VEG]:
        return (prod_qty or 1000, "g")
    return qty, unit

def fill_missing_logical(df):
    for product in df["product_clean"].unique():
        sub = df[df["product_clean"] == product]
        if sub["quantity"].notna().any():
            mean_qty = int(sub["quantity"].dropna().mean())
            unit = sub["unit_normalized"].dropna().iloc[0]
            df.loc[(df["product_clean"] == product) & df["quantity"].isna(), "quantity"] = mean_qty
            df.loc[(df["product_clean"] == product) & df["unit_normalized"].isna(), "unit_normalized"] = unit
    return df

def unify_units(df):
    df = df.copy()
    df = fill_missing_logical(df)
    fixed = df.apply(fix_logical_units, axis=1, result_type="expand")
    df["quantity"], df["unit_normalized"] = fixed[0], fixed[1]
    return df

# ────────────────────────────────────────────────────────────────
# Очистка одного файла
# ────────────────────────────────────────────────────────────────

def clean_file(path):
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    if "found_name" in df.columns:
        df.drop(columns=["found_name"], inplace=True)

    df["store"] = df["store"].apply(remove_invisible_chars)
    df["product"] = df["product"].apply(remove_invisible_chars)
    df["price"] = df["price"].apply(parse_price).apply(lambda x: "No price" if pd.isna(x) else x)

    parsed = df["unit"].apply(normalize_unit)
    df["quantity"] = parsed.apply(lambda x: x[0])
    df["unit_normalized"] = parsed.apply(lambda x: x[1])

    df["brand"] = df["product"].apply(extract_brand)
    df["product_clean"] = df["product"].apply(clean_product_name)

    df = df.apply(fix_logical_units, axis=1, result_type="expand").assign(
        quantity=lambda x: x[0],
        unit_normalized=lambda x: x[1]
    )

    df.drop(columns=["unit"], errors="ignore", inplace=True)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    return df[df["product_clean"].notna()]

# ────────────────────────────────────────────────────────────────
# Основной пайплайн
# ────────────────────────────────────────────────────────────────

def transform_all():
    if not os.path.exists(RAW_DIR):
        print("RAW_DIR не найден, пропуск трансформации")
        return

    frames = []
    for file in os.listdir(RAW_DIR):
        if file.endswith(".csv"):
            try:
                df = clean_file(os.path.join(RAW_DIR, file))
                frames.append(df)
                print(f"[OK] cleaned {file} ({len(df)} строк)")
            except Exception as e:
                print(f"[ERROR] {file} → {e}")

    if not frames:
        print("No data to process")
        return

    full_df = pd.concat(frames, ignore_index=True)
    full_df = unify_units(full_df)
    full_df = full_df[["store", "product_clean", "brand", "price", "quantity", "unit_normalized", "date"]]

    output_path = os.path.join(CLEAN_DIR, "clean_prices.csv")
    full_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {output_path}")

# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    transform_all()
