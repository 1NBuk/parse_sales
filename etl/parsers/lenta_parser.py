import time
import pandas as pd
import re
from datetime import datetime
from rapidfuzz import fuzz
from urllib.parse import quote
import os
import sys

# Добавляем путь к utils в sys.path
sys.path.append(os.path.dirname(__file__))

try:
    from xdriver_utils import create_driver
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "driver_utils",
        os.path.join(os.path.dirname(__file__), "xdriver_utils.py")
    )
    driver_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver_utils)
    create_driver = driver_utils.create_driver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================= НАСТРОЙКИ =================
PRODUCTS = [
    "Яйцо куриное Окское С1 10шт",
    "Батон Коломенский Нарезной 200г",
    "Молоко Простоквашино отборное пастеризованное",
    "Сахар кусковой белый 1кг",
    "Соль пищевая 1кг",
    "Крупа гречневая Мистраль 900г",
    "Масло Олейна подсолнечное 1л",
    "Масло Брест-Литовск сливочное 82,5% 180г",
    "Филе грудки цыпленка Петелинка",
    "Чай Greenfield Golden Ceylon 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь весовая",
    "Капуста белокочанная",
    "Яблоки сезонные"
]

WEIGHT_PRODUCTS = [
    "Картофель",
    "Лук репчатый",
    "Морковь",
    "Капуста белокочанная",
    "Яблоки сезонные"
]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
OUTPUT_FILE = os.path.join(BASE_DIR, "lenta_prices.csv")
os.makedirs(BASE_DIR, exist_ok=True)

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================

def close_popups(driver):
    """Закрытие всплывающих окон на сайте Ленты"""
    selectors = [
        "button.popup__close",
        "div.flocktory-widget-overlay",
        "div.modal button",
        "[aria-label='Close']",
        ".close-btn"
    ]
    for selector in selectors:
        for el in driver.find_elements(By.CSS_SELECTOR, selector):
            try:
                driver.execute_script("arguments[0].click();", el)
            except:
                continue

def search_product(driver, product_name):
    """Поиск товара на сайте Ленты"""
    encoded_query = quote(product_name, safe='')
    search_url = f"https://lenta.com/search/{encoded_query}/"
    driver.get(search_url)
    time.sleep(2)
    close_popups(driver)

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "lu-product-card"))
        )
    except:
        return []

    cards = driver.find_elements(By.CSS_SELECTOR, "lu-product-card")
    results = []

    for card in cards[:15]:
        try:
            name_elem = card.find_element(By.CSS_SELECTOR, "span.card-name_content")
            name = name_elem.text.strip()

            # Единица измерения
            unit = None
            try:
                unit_elem = card.find_element(By.CSS_SELECTOR, "p.card-name_package")
                unit = unit_elem.text.strip()
            except:
                match = re.search(r'(\d+[.,]?\d*\s*(?:кг|г|л|мл|шт|мг|таб|пач|уп|упак))', name, re.IGNORECASE)
                unit = match.group(1) if match else "1000г"

            price = None
            if any(wp.lower() in product_name.lower() for wp in WEIGHT_PRODUCTS):
                try:
                    price_elem = card.find_element(By.CSS_SELECTOR, "span.price")
                    price_text = price_elem.text.strip()
                    price_match = re.search(r'(\d+[.,]?\d+)', price_text)
                    if price_match:
                        price = price_match.group(1)
                        unit_match = re.search(r'за\s*(\d+[.,]?\s*(?:кг|г))', price_text, re.IGNORECASE)
                        if unit_match:
                            unit = unit_match.group(1)
                except:
                    pass

            if not price:
                try:
                    price_elem = card.find_element(By.CSS_SELECTOR, "span.main-price")
                    price_text = price_elem.text.strip()
                    price_match = re.search(r'(\d+[.,]\d+|\d+)', price_text)
                    if price_match:
                        price = price_match.group(0)
                except:
                    for pat in [r'(\d+[.,]\d+)\s*₽', r'(\d+)\s*₽']:
                        m = re.search(pat, card.text)
                        if m:
                            price = m.group(1)
                            break

            results.append({"name": name, "unit": unit, "price": price})
        except:
            continue

    return results

def clean_price(price_text):
    """Конвертация цены в число"""
    if not price_text:
        return None
    try:
        cleaned = re.sub(r'[^\d.,]', '', str(price_text)).replace(',', '.')
        return float(cleaned)
    except:
        return None

def find_best_match(product_name, items):
    """Выбор лучшего совпадения с помощью RapidFuzz"""
    if not items:
        return None, 0
    best_match, best_score = None, 0
    for item in items:
        scores = [
            fuzz.token_set_ratio(product_name.lower(), item['name'].lower()),
            fuzz.partial_ratio(product_name.lower(), item['name'].lower())
        ]
        score = max(scores)
        if item['price']:
            score += 10
        if score > best_score:
            best_score = score
            best_match = item
    return best_match, best_score

# ================= ОСНОВНОЙ КОД =================

def main():
    results_final = []
    today = datetime.today().strftime("%Y-%m-%d")
    driver = create_driver(use_uc=True)

    try:
        for product in PRODUCTS:
            print(f"\nИщем: {product}")
            items = search_product(driver, product)
            best_match, score = find_best_match(product, items)

            save_name = re.sub(r'\s*сезонные', '', product, flags=re.IGNORECASE)

            if best_match and score >= 50:
                results_final.append({
                    "store": "Лента",
                    "product": save_name,
                    "unit": best_match["unit"],
                    "price": clean_price(best_match["price"]),
                    "date": today
                })
                print(f"Выбрано: {best_match['name']} - {best_match['price']} - {best_match['unit']} (score: {score:.1f})")
            else:
                results_final.append({
                    "store": "Лента",
                    "product": save_name,
                    "unit": "1000г",
                    "price": None,
                    "date": today
                })
                print(f"Не найдено: {product} (score: {score:.1f})")

            time.sleep(1)

    finally:
        driver.quit()

    df = pd.DataFrame(results_final)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\nСохранено {len(df)} записей в {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
