import time
import re
import os
import sys
import pandas as pd
from datetime import datetime
from rapidfuzz import fuzz
from urllib.parse import quote

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
    "Морковь",
    "Капуста белокочанная",
    "Яблоки сезонные"
]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
OUTPUT_FILE = os.path.join(BASE_DIR, "lenta_prices.csv")
os.makedirs(BASE_DIR, exist_ok=True)


def clean_price(text):
    m = re.search(r"(\d+[.,]?\d*)", text or "")
    return m.group(1).replace(",", ".") if m else None


def main():
    results = []
    today = datetime.today().strftime("%Y-%m-%d")
    driver = create_driver(use_uc=True)
    wait = WebDriverWait(driver, 20)

    try:
        for product in PRODUCTS:
            print(f"Ищем: {product}")
            url = f"https://lenta.com/search/{quote(product)}/"
            driver.get(url)

            try:
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "lu-product-card")
                    )
                )

                cards = driver.find_elements(By.CSS_SELECTOR, "lu-product-card")
                best = None
                best_score = -1

                for card in cards[:20]:
                    try:
                        name = card.text
                        score = fuzz.token_sort_ratio(product.lower(), name.lower())
                        if score > best_score:
                            best_score = score
                            best = card
                    except:
                        continue

                if not best or best_score < 40:
                    print(f"Не найдено: {product}")
                    results.append({
                        "store": "Лента",
                        "product": product,
                        "unit": "1 кг",
                        "price": None,
                        "date": today
                    })
                    continue

                price = clean_price(best.text)
                unit_match = re.search(r"(\d+\s?(г|кг|мл|л|шт))", best.text)
                unit = unit_match.group(1) if unit_match else "1 кг"

                print(f"Лента — {product} — {price} ₽ — {unit} (score={best_score})")

                results.append({
                    "store": "Лента",
                    "product": product,
                    "unit": unit,
                    "price": price,
                    "date": today
                })

            except Exception as e:
                print(f"Ошибка: {product}: {e}")
                results.append({
                    "store": "Лента",
                    "product": product,
                    "unit": "1 кг",
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
