import pandas as pd
import os
import re
import numpy as np

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
    "брест литовск",
    "олейна",
    "greenfield",
    "коломенский",
    "мистраль",
    "петелинка"
]

# Словарь для нормализации названий магазинов
STORE_MAPPING = {
    "ашан": "Ашан",
    "дикси": "Дикси",
    "доставка dixy": "Дикси",
    "глобус": "Глобус",
    "лента": "Лента",
    "магнит": "Магнит",
    "перекресток": "Перекресток",
    "мегамаркет": "Мегамаркет",
    "ozon": "OZON",
    "wildberries": "Wildberries",
    "яндекс маркет": "Яндекс Маркет",
    "samokat.ru": "Самокат",
    "kuper.ru": "Купер",
    "av.ru": "Азбука Вкуса",
    "myspar.ru": "Спар",
    "vodovoz.ru": "Водовоз",
    "online.metro-cc.ru": "METRO",
    "5ka.ru": "Пятёрочка",
    "fix-price.com": "Fix Price",
    "bristol.ru": "Бристоль"
}

# Словарь для нормализации названий продуктов
PRODUCT_MAPPING = {
    "яйцо": "Яйцо куриное",
    "яйца": "Яйцо куриное",
    "молоко": "Молоко",
    "батон": "Батон",
    "хлеб": "Батон",
    "сахар": "Сахар",
    "соль": "Соль",
    "гречка": "Крупа гречневая",
    "гречневая крупа": "Крупа гречневая",
    "масло подсолнечное": "Масло подсолнечное",
    "масло сливочное": "Масло сливочное",
    "куриное филе": "Филе куриное",
    "филе грудки": "Филе куриное",
    "петелинка": "Филе куриное",
    "чай": "Чай",
    "картофель": "Картофель",
    "лук": "Лук",
    "морковь": "Морковь",
    "капуста": "Капуста",
    "яблоки": "Яблоки"
}

# Словарь соответствия брендов для продуктов, где бренд не указан явно
PRODUCT_BRAND_MAPPING = {
    "Чай": "Greenfield",
    "Масло подсолнечное": "Олейна",
    "Масло сливочное": "Брест-Литовск",
    "Крупа гречневая": "Мистраль",
    "Яйцо куриное": "Окское",
    "Молоко": "Простоквашино",
    "Батон": "Коломенский"
}

# Ключевые слова для исключения (семена, посадочный материал)
EXCLUDE_KEYWORDS = [
    "семена", "посадку", "сорт", "гибрид", "рассада", "селекция",
    "саженцы", "луковицы", "клубни", "корневища", "семенной"
]

# Минимальные допустимые значения quantity для разных категорий (в граммах)
MIN_QUANTITY = {
    "Картофель": 100,
    "Лук": 100,
    "Морковь": 100,
    "Капуста": 100,
    "Яблоки": 100,
    "Чай": 20,
    "Сахар": 100,
    "Соль": 100,
    "Крупа гречневая": 100,
    "Масло подсолнечное": 100,
    "Масло сливочное": 50,
    "Филе куриное": 100
}


def remove_invisible_chars(text):
    """Удаляет невидимые и спецсимволы из текста"""
    if pd.isna(text):
        return None
    # Убираем невидимые символы типа \u200b, \u2060, ⁠ и прочие
    text = re.sub(r"[\u200B-\u200D\u2060\uFEFF⁠]", "", str(text))
    text = text.strip()
    return text if text else None


def parse_price(value):
    """Парсит цену и возвращает float или None"""
    if pd.isna(value) or str(value).strip() == "" or str(value).strip() == "No price":
        return None
    value = str(value).replace("₽", "").replace(" ", "").replace(",", ".")
    # Извлекаем первое число из строки
    match = re.search(r"(\d+\.?\d*)", value)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def extract_weight_from_text(text):
    """Извлекает количество и единицу измерения из текста"""
    if pd.isna(text):
        return None, None
    text = str(text).lower().replace(" ", "").replace(",", ".")
    # Ищем паттерны типа "1000г", "1кг", "930мл", "10шт" и т.д.
    match = re.search(r"(\d+(\.\d+)?)\s*(кг|г|гр|мл|л|шт)?", text)
    if not match:
        return None, None

    qty = float(match.group(1))
    unit = match.group(3) if match.group(3) else ""

    # Стандартизируем единицы
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


def normalize_store(store):
    """Приводит название магазина к каноничному виду"""
    if pd.isna(store):
        return None

    text = remove_invisible_chars(store)
    if not text:
        return None

    text_lower = text.lower().strip()

    # Проверяем по словарю
    for key, value in STORE_MAPPING.items():
        if key in text_lower:
            return value

    # Если не нашли, возвращаем оригинал (но без лишних символов)
    return text


def extract_brand(name, product_clean=None):
    """Определяет бренд по названию продукта"""
    if pd.isna(name) or str(name).strip() == "":
        return "No Brand"

    text = str(name).lower()

    # Проверяем известные бренды
    for brand in KNOWN_BRANDS:
        brand_lower = brand.lower()
        if brand_lower in text:
            # Специальная обработка для "брест-литовск"
            if "брест" in text and "литовск" in text:
                return "Брест-Литовск"
            return brand.title()

    # Если бренд не найден, но есть очищенное название продукта,
    # пробуем подставить стандартный бренд для этого продукта
    if product_clean and product_clean in PRODUCT_BRAND_MAPPING:
        return PRODUCT_BRAND_MAPPING[product_clean]

    return "No Brand"


def clean_product_name(name):
    """Приводит название продукта к каноничному виду"""
    if pd.isna(name):
        return None

    text = remove_invisible_chars(str(name))
    if not text:
        return None

    text_lower = text.lower()

    # Проверяем по словарю продуктов
    for key, value in PRODUCT_MAPPING.items():
        if key in text_lower:
            return value

    # Если не нашли в словаре, пробуем извлечь основное слово
    # Убираем цифры, спецсимволы и лишние слова
    text_clean = re.sub(r'\d+[\s]*[кггмллшт]?', '', text_lower)
    text_clean = re.sub(r'[^\w\s]', ' ', text_clean)
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()

    # Если после очистки осталось что-то осмысленное
    if text_clean and len(text_clean) > 2:
        return text_clean.title()

    return None


def is_excluded_product(name):
    """Проверяет, нужно ли исключить продукт (семена, посадочный материал)"""
    if pd.isna(name):
        return False

    text = str(name).lower()
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in text:
            return True
    return False


def fix_quantity_anomalies(quantity, unit, product):
    """Исправляет аномальные значения quantity"""
    if pd.isna(quantity) or pd.isna(unit):
        return quantity, unit

    product_lower = str(product).lower() if product else ""

    # Получаем дефолтные значения
    default_qty, default_unit = get_default_quantity_unit(product)

    # Критические аномалии для разных категорий
    if "молоко" in product_lower and unit == "ml":
        if quantity > 5000:  # Больше 5 литров - явная ошибка
            return 930, "ml"

    # Для овощей и фруктов
    veg_fruits = ["картофель", "лук", "морковь", "капуста", "яблоки"]
    if any(fv in product_lower for fv in veg_fruits):
        if unit == "pcs" and quantity < 10:  # Штуки вместо килограмма
            return 1000, "g"
        if unit == "g" and quantity < 10:  # Слишком мало грамм
            return 1000, "g"
        if unit == "g" and quantity > 10000:  # Больше 10 кг - слишком много
            return 1000, "g"

    # Для чая
    if "чай" in product_lower:
        if unit == "pcs":  # Чай в штуках - ошибка
            return 100, "g"
        if unit == "g" and quantity < 20:  # Слишком мало грамм
            return 100, "g"

    # Для масла сливочного
    if "масло сливочное" in product_lower and unit == "g":
        if quantity < 50:  # Слишком мало
            return 180, "g"
        if quantity > 500:  # Слишком много
            return 180, "g"

    return quantity, unit


def get_default_quantity_unit(product):
    """Возвращает стандартные quantity и unit для продукта"""
    product_lower = str(product).lower() if product else ""

    defaults = {
        "яйцо куриное": (10, "pcs"),
        "молоко": (930, "ml"),
        "батон": (200, "g"),
        "сахар": (1000, "g"),
        "соль": (1000, "g"),
        "крупа гречневая": (900, "g"),
        "масло подсолнечное": (1000, "ml"),
        "масло сливочное": (180, "g"),
        "филе куриное": (1000, "g"),
        "чай": (100, "g"),
        "картофель": (1000, "g"),
        "лук": (1000, "g"),
        "морковь": (1000, "g"),
        "капуста": (1000, "g"),
        "яблоки": (1000, "g")
    }

    for key, (default_qty, default_unit) in defaults.items():
        if key in product_lower:
            return default_qty, default_unit

    return None, None


def fix_logical_units(row):
    """
    Исправляет логические единицы измерения по типу продукта
    """
    product = row.get("product_clean", "")
    qty = row.get("quantity")
    unit = row.get("unit_normalized")

    if pd.isna(product):
        return qty, unit

    # Получаем дефолтные значения для продукта
    default_qty, default_unit = get_default_quantity_unit(product)

    # Если нет количества или единицы, ставим дефолтные
    if pd.isna(qty) or pd.isna(unit):
        if default_qty is not None:
            return default_qty, default_unit
        return qty, unit

    # Исправляем аномалии
    qty, unit = fix_quantity_anomalies(qty, unit, product)

    return qty, unit


def fill_missing_prices(df):
    """Заполняет пропущенные цены средними по продукту"""
    df = df.copy()

    for product in df['product_clean'].unique():
        mask = (df['product_clean'] == product) & (df['price'].isna())
        if mask.any():
            # Берем среднюю цену для этого продукта, исключая выбросы
            prices = df[df['product_clean'] == product]['price'].dropna()
            if not prices.empty:
                # Отсекаем выбросы (цены, отклоняющиеся более чем на 3 стандартных отклонения)
                mean_price = prices.mean()
                std_price = prices.std()
                if std_price > 0:
                    valid_prices = prices[abs(prices - mean_price) <= 3 * std_price]
                    if not valid_prices.empty:
                        avg_price = valid_prices.mean()
                    else:
                        avg_price = mean_price
                else:
                    avg_price = mean_price

                df.loc[mask, 'price'] = round(avg_price, 2)

    return df


def select_closest_to_previous(df):
    """
    Для каждой группы (store, product_clean, brand, date)
    выбирает запись, наиболее похожую на предыдущий день
    """
    df = df.sort_values("date")
    result_rows = []

    group_cols = ["store", "product_clean", "brand"]

    for keys, group in df.groupby(group_cols):
        group = group.sort_values("date")

        prev_price = None
        prev_qty = None

        for date, day_group in group.groupby("date"):

            if len(day_group) == 1:
                chosen = day_group.iloc[0]

            else:
                day_group = day_group.copy()

                if prev_price is not None and prev_qty is not None:
                    # основной сценарий — сравнение с предыдущим днем
                    day_group["score"] = (
                        (day_group["price"] - prev_price).abs().fillna(1e6) +
                        (day_group["quantity"] - prev_qty).abs().fillna(1e6)
                    )

                else:
                    # fallback — если нет предыдущего дня
                    default_qty, _ = get_default_quantity_unit(keys[1])

                    if default_qty is not None:
                        day_group["score"] = (
                            (day_group["quantity"] - default_qty).abs().fillna(1e6)
                        )
                    else:
                        # если вообще нет дефолта → используем цену
                        median_price = day_group["price"].median()
                        day_group["score"] = (
                            (day_group["price"] - median_price).abs().fillna(1e6)
                        )

                chosen = day_group.sort_values("score").iloc[0]

            result_rows.append(chosen)

            prev_price = chosen["price"]
            prev_qty = chosen["quantity"]

    return pd.DataFrame(result_rows)

def clean_file(path):
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    # Убираем лишние колонки
    if "found_name" in df.columns:
        df = df.drop(columns=["found_name"])

    # Обрабатываем store
    df["store"] = df["store"].apply(normalize_store)

    # Обрабатываем product (убираем невидимые символы)
    df["product"] = df["product"].apply(remove_invisible_chars)

    # Исключаем семена и посадочный материал
    df = df[~df["product"].apply(is_excluded_product)]

    # Обрабатываем цену
    df["price"] = df["price"].apply(parse_price)

    # Парсим единицы измерения из колонки unit
    if "unit" in df.columns:
        parsed = df["unit"].apply(extract_weight_from_text)
        df["quantity"] = parsed.apply(lambda x: x[0])
        df["unit_normalized"] = parsed.apply(lambda x: x[1])
    else:
        df["quantity"] = None
        df["unit_normalized"] = None

    # Очищаем название продукта
    df["product_clean"] = df["product"].apply(clean_product_name)

    # Удаляем строки без очищенного названия
    df = df[df["product_clean"].notna()].copy()

    # Определяем бренд (теперь с учетом очищенного названия)
    df["brand"] = df.apply(lambda row: extract_brand(row["product"], row["product_clean"]), axis=1)

    # Применяем логические исправления
    fixed = df.apply(fix_logical_units, axis=1, result_type="expand")
    df["quantity"] = fixed[0]
    df["unit_normalized"] = fixed[1]

    # Удаляем колонку unit если она есть
    df = df.drop(columns=["unit"], errors="ignore")

    # Обрабатываем дату
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    return df[["store", "product_clean", "brand", "price", "quantity", "unit_normalized", "date"]]


# ────────────────────────────────────────────────────────────────
# Основной пайплайн
# ────────────────────────────────────────────────────────────────

def transform_all():
    frames = []
    for file in os.listdir(RAW_DIR):
        if file.endswith(".csv"):
            try:
                df = clean_file(os.path.join(RAW_DIR, file))
                if not df.empty:
                    frames.append(df)
                    print(f"[OK] cleaned {file} ({len(df)} rows)")
                else:
                    print(f"[WARN] {file} is empty after cleaning")
            except Exception as e:
                print(f"[ERROR] {file} → {e}")

    if not frames:
        print("No data to process")
        return

    frames = [f for f in frames if not f.empty]
    full_df = pd.concat(frames, ignore_index=True)
    full_df["price"] = pd.to_numeric(full_df["price"], errors="coerce")
    full_df["quantity"] = pd.to_numeric(full_df["quantity"], errors="coerce")
    full_df = full_df.replace("", None)
    for idx, row in full_df.iterrows():
        qty, unit = fix_quantity_anomalies(row["quantity"], row["unit_normalized"], row["product_clean"])
        full_df.at[idx, "quantity"] = qty
        full_df.at[idx, "unit_normalized"] = unit

    # Заполняем пропущенные цены
    full_df = fill_missing_prices(full_df)

    full_df = select_closest_to_previous(full_df)

    # Сортируем и сохраняем
    full_df = full_df.sort_values(["store", "product_clean"])
    full_df = full_df[["store", "product_clean", "brand", "price", "quantity", "unit_normalized", "date"]]

    output_path = os.path.join(CLEAN_DIR, "clean_prices.csv")
    full_df = full_df.replace({np.nan: None})
    full_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {output_path} ({len(full_df)} rows)")


# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    transform_all()