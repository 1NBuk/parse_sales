import time
import os
import re
import urllib.parse
import pandas as pd
from datetime import datetime
from rapidfuzz import fuzz
import sys

# Добавляем путь к utils
sys.path.append(os.path.dirname(__file__))

try:
    from etl.driver_utils import create_driver
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
    "Чай Greenfield Золотой Цейлон 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь",
    "Капуста белокочанная",
    "Яблоки сезонные"
]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
os.makedirs(BASE_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(BASE_DIR, "pyaterochka_prices.csv")

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================

def split_name_unit(product: str):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""

def warmup_site(driver):
    driver.get("https://5ka.ru")
    time.sleep(5)

def parse_product(driver, product, is_first=False):
    name_only, unit_default = split_name_unit(product)
    unit_default = unit_default or "1 кг"
    encoded_query = urllib.parse.quote(product)
    url = f"https://5ka.ru/search/?text={encoded_query}"

    attempts = 2 if is_first else 1
    for attempt in range(attempts):
        if attempt > 0:
            print("Повторная попытка для первого товара...")
            time.sleep(3)

        driver.get(url)
        time.sleep(2)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.css-i9gxme"))
            )
            cards = driver.find_elements(By.CSS_SELECTOR, "div.css-i9gxme")
            selected_card = None
            max_score = 0

            for card in cards:
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, "div.css-9ncz4i p[type='text']")
                    title_text = title_elem.text.strip().lower()
                    score = fuzz.token_sort_ratio(name_only.lower(), title_text)
                    if score > max_score:
                        max_score = score
                        selected_card = card
                except:
                    continue

            if not selected_card or max_score < 50:
                continue

            # Цена
            price = None
            try:
                spans = selected_card.find_elements(By.CSS_SELECTOR, "div.css-1gnr8ln span")
                if len(spans) >= 2:
                    price = f"{spans[0].text.strip()},{spans[1].text.strip()} ₽"
            except:
                pass

            # Единица
            try:
                unit_elem = selected_card.find_element(By.CSS_SELECTOR, "div.css-p5esxm > p[type='caption']")
                unit = unit_elem.text.strip() if unit_elem.text.strip() else unit_default
            except:
                unit = unit_default

            print(f"{name_only} — {price} — {unit} (score: {max_score})")
            return {"store": "Пятерочка", "product": product, "unit": unit, "price": price, "date": datetime.today().strftime("%Y-%m-%d")}

        except:
            continue

    print(f"Пятерочка — {name_only} — товар не найден")
    return {"store": "Пятерочка", "product": product, "unit": unit_default, "price": None, "date": datetime.today().strftime("%Y-%m-%d")}

# ================= ОСНОВНОЙ КОД =================

def main():
    results = []
    driver = create_driver(use_uc=True)
    time.sleep(5)
    warmup_site(driver)

    try:
        for idx, product in enumerate(PRODUCTS):
            result = parse_product(driver, product, is_first=(idx == 0))
            results.append(result)
            time.sleep(1)

    finally:
        driver.quit()

    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\nСохранено {len(df)} записей в {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
