import time
import pandas as pd
from datetime import datetime
import re
import urllib.parse
import os
import sys

# Добавляем путь к utils
sys.path.append(os.path.dirname(__file__))

try:
    from driver_utils import create_driver
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "driver_utils",
        os.path.join(os.path.dirname(__file__), "driver_utils.py")
    )
    driver_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver_utils)
    create_driver = driver_utils.create_driver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz

# ================= НАСТРОЙКИ =================
PRODUCTS = [
    "Яйцо куриное Окское отборное С1 10шт",
    "Батон Коломенский Нарезной 200г",
    "Молоко Простоквашино отборное пастеризованное 3.4-4.5%",
    "Сахар кусковой белый 1кг",
    "Соль пищевая 1кг",
    "Крупа гречневая Мистраль 900г",
    "Масло Олейна подсолнечное 1л",
    "Масло Брест-Литовск сливочное 82,5% 180г",
    "Филе грудки цыпленка Петелинка",
    "Чай Greenfield Golden Ceylon 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь",
    "Капуста белокочанная",
    "Яблоки сезонные"
]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
OUTPUT_FILE = os.path.join(BASE_DIR, "dixy_prices.csv")
os.makedirs(BASE_DIR, exist_ok=True)

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def split_name_unit(product: str):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        unit = match.group(1)
        name = product.replace(unit, "").strip()
    else:
        unit = ""
        name = product
    return name, unit

def parse_price(card):
    """Парсинг цены из карточки товара"""
    try:
        price_block = card.find_element(By.CSS_SELECTOR, "div.card__price-num")
        # Основная часть цены
        main_part = re.search(r'\d+', price_block.text)
        main_part = main_part.group() if main_part else "0"
        # Дробная часть
        spans = price_block.find_elements(By.TAG_NAME, "span")
        frac_part = spans[0].text.strip() if spans else "00"
        return f"{main_part},{frac_part} ₽"
    except:
        return None

def extract_unit(text, default_unit):
    try:
        match_unit = re.search(r"(\d+\s?(г|кг|мл|л|шт))", text)
        return match_unit.group(1) if match_unit else default_unit or "1000 гр"
    except:
        return default_unit or "1000 гр"

# ================= ОСНОВНОЙ КОД =================
def main():
    results = []
    today = datetime.today().strftime("%Y-%m-%d")
    driver = create_driver(use_uc=False)  # Для Дикси используем обычный драйвер

    try:
        for product in PRODUCTS:
            name_only, unit_default = split_name_unit(product)
            encoded_query = urllib.parse.quote(product)
            url = f"https://dixy.ru/catalog/?q={encoded_query}"
            driver.get(url)
            time.sleep(2)  # Ждем загрузку страницы

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article.card.bs-state"))
                )
                cards = driver.find_elements(By.CSS_SELECTOR, "article.card.bs-state")
                selected_card = None
                max_score = 0

                # Выбираем карточку с максимальным совпадением
                for card in cards:
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, "p.card__title")
                        title_text = title_elem.text.strip().lower()
                        score = fuzz.token_sort_ratio(name_only.lower(), title_text)
                        if score > max_score:
                            max_score = score
                            selected_card = card
                    except:
                        continue

                if selected_card and max_score > 20:
                    price = parse_price(selected_card)
                    unit_from_site = extract_unit(selected_card.text, unit_default)

                    results.append({
                        "store": "Дикси",
                        "product": product,
                        "unit": unit_from_site,
                        "price": price,
                        "date": today
                    })
                    print(f"{name_only} — {price} — {unit_from_site} (score: {max_score})")
                else:
                    print(f"Дикси — {name_only} — товар не найден (max score {max_score})")
                    results.append({
                        "store": "Дикси",
                        "product": product,
                        "unit": unit_default or "1000 гр",
                        "price": None,
                        "date": today
                    })

            except Exception as e:
                print(f"Дикси — {name_only} — ошибка: {e}")
                results.append({
                    "store": "Дикси",
                    "product": product,
                    "unit": unit_default or "1000 гр",
                    "price": None,
                    "date": today
                })

            time.sleep(2)

    finally:
        driver.quit()

    # Сохраняем CSV
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"Сохранено {len(df)} записей в {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
