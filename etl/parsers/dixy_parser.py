import time
import re
import os
import sys
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)
import pandas as pd
from datetime import datetime
from urllib.parse import quote
from rapidfuzz import fuzz
import json

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

if len(sys.argv) > 1:
    try:
        products = json.loads(sys.argv[1])  # ожидаем JSON-строку
    except:
        products = [sys.argv[1]]
else:
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
        "Яблоки Гала"
    ]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
OUTPUT_FILE = os.path.join(BASE_DIR, "dixy_prices.csv")
os.makedirs(BASE_DIR, exist_ok=True)


def split_name_unit(product: str):
    m = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.I)
    if m:
        return product.replace(m.group(1), "").strip(), m.group(1)
    return product, "1 кг"


def parse_price(card):
    try:
        price_el = card.find_element(By.CSS_SELECTOR, "[class*='price']")
        m = re.search(r"(\d+[.,]?\d*)", price_el.text)
        if m:
            return m.group(1).replace(",", ".")
    except:
        pass
    return None


def main():
    results = []
    today = datetime.today().strftime("%Y-%m-%d")
    driver = create_driver(use_uc=False)
    wait = WebDriverWait(driver, 15)

    try:
        for product in PRODUCTS:
            name_only, unit_default = split_name_unit(product)
            url = f"https://dixy.ru/catalog/?q={quote(product)}"
            driver.get(url)

            try:
                wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "article [class*='title'], article [class*='name']")
                    )
                )

                cards = driver.find_elements(By.CSS_SELECTOR, "article")
                best_card = None
                best_score = -1

                for card in cards:
                    try:
                        try:
                            title_el = card.find_element(By.CSS_SELECTOR, "[class*='title'], [class*='name']")
                            title = title_el.text.strip()
                        except:
                            continue
                        score = fuzz.token_sort_ratio(name_only.lower(), title.lower())
                        if score > best_score:
                            best_score = score
                            best_card = card
                    except:
                        continue

                if not best_card or best_score < 20:
                    print(f"Дикси — {product} — товар не найден")
                    results.append({
                        "store": "Дикси",
                        "product": product,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                price = parse_price(best_card)
                unit_match = re.search(r"(\d+\s?(г|кг|мл|л|шт))", best_card.text)
                unit = unit_match.group(1) if unit_match else unit_default

                print(f"Дикси — {product} — {price} ₽ — {unit} (score={best_score})")

                results.append({
                    "store": "Дикси",
                    "product": product,
                    "unit": unit,
                    "price": price,
                    "date": today
                })

            except Exception as e:
                print(f"Дикси — {product} — ошибка: {e}")
                results.append({
                    "store": "Дикси",
                    "product": product,
                    "unit": unit_default,
                    "price": None,
                    "date": today
                })

            time.sleep(2)

    finally:
        driver.quit()

    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"Сохранено {len(results)} записей в {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
