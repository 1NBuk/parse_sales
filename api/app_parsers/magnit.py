import time
import os
import sys
import random
import re
import urllib.parse
from datetime import datetime
import json
import pandas as pd
import logging
import warnings
import sys
import io
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
# ===================== НАСТРОЙКА =====================
warnings.filterwarnings("ignore")
logging.getLogger("selenium").setLevel(logging.CRITICAL)


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)

from etl.driver_utils import create_driver

# ===================== INPUT =====================
def read_products():
    try:
        data = sys.stdin.read()
        if data:
            return json.loads(data)
    except:
        pass
    return []

PRODUCTS = read_products()

if not PRODUCTS:
    PRODUCTS = [
        "Яйцо С1 10шт",
        "Молоко 1л",
        "Хлеб 500г"
    ]

TARGET_ADDRESS = "Панфилова 2"

# ===================== UTILS =====================
def log(msg):
    print(msg, file=sys.stderr)

def human_delay(a=0.5, b=1.2):
    time.sleep(random.uniform(a, b))

def normalize_query(text):
    return re.sub(r"\d+(\.\d+)?\s?(г|кг|мл|л|шт)", "", text, flags=re.I).strip()

def extract_unit(text):
    m = re.search(r"\d+\s?(г|кг|мл|л|шт)", text, re.I)
    return m.group(0) if m else ""

def safe_get(driver, url):
    driver.get(url)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

def scroll_all(driver):
    last = 0
    while True:
        height = driver.execute_script("return document.body.scrollHeight")
        if height == last:
            break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        last = height

# ===================== STORE =====================
def ensure_store_selected(driver, address):
    try:
        log("Выбираем магазин...")

        bar = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "div.pl-shop-select-bar[data-test-id='map-button']")
            )
        )
        bar.click()
        time.sleep(1)

        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[text()='Выберите магазин']]")
                )
            )
            btn.click()
        except:
            pass

        address_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//input[@placeholder='Адрес магазина']")
            )
        )

        address_input.clear()
        address_input.send_keys(address)
        time.sleep(2)

        try:
            choose_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(., 'Выбрать')]")
                )
            )
            choose_btn.click()
        except:
            shop_item = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".pl-shop-item, [data-test-id='shop-item']")
                )
            )
            shop_item.click()

        time.sleep(3)
        log(f"OK магазин: {address}")

    except Exception as e:
        log(f"Ошибка выбора магазина: {e}")

# ===================== PARSE =====================
def parse_card(card, default_unit):
    try:
        title = card.find_element(
            By.CSS_SELECTOR,
            ".unit-catalog-product-preview-title"
        ).text.strip()
    except:
        return None

    try:
        text = card.text
        m = re.search(r"(\d+[.,]?\d*)", text)
        price = m.group(1).replace(",", ".") if m else None
    except:
        price = None

    unit = extract_unit(title) or default_unit or "1 шт"

    return title, price, unit

# ===================== MAIN =====================
def main():
    results = []
    today = datetime.today().strftime("%Y-%m-%d")

    driver = None

    try:
        driver = create_driver(use_uc=True)

        log("Открываем сайт...")
        safe_get(driver, "https://magnit.ru/")
        time.sleep(3)

        ensure_store_selected(driver, TARGET_ADDRESS)

        for product in PRODUCTS:
            try:
                product = product.strip()
                query = normalize_query(product)
                default_unit = extract_unit(product)

                log(f"Ищем: {product}")

                url = f"https://magnit.ru/search/?term={urllib.parse.quote(query)}"
                safe_get(driver, url)
                time.sleep(2)

                scroll_all(driver)

                cards = WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, ".unit-catalog-product-preview")
                    )
                )

                best = None
                best_score = -1

                for card in cards[:5]:
                    try:
                        parsed = parse_card(card, default_unit)
                        if not parsed:
                            continue

                        title, price, unit = parsed

                        # УПРОЩЁННЫЙ scoring (как во втором коде)
                        score = len(set(query.lower().split()) &
                                    set(title.lower().split()))

                        if score > best_score:
                            best_score = score
                            best = (title, price, unit)

                    except:
                        continue

                if not best:
                    raise Exception("Не найдено")

                title, price, unit = best

                results.append({
                    "store": "Магнит",
                    "product": product,
                    "found_name": title,
                    "price": price,
                    "unit": unit,
                    "date": today
                })

                log(f"OK: {product} -> {price}")

            except Exception as e:
                log(f"Ошибка: {product} -> {e}")
                results.append({
                    "store": "Магнит",
                    "product": product,
                    "found_name": None,
                    "price": None,
                    "unit": "1 шт",
                    "date": today
                })

            time.sleep(random.uniform(2, 4))

    except Exception as e:
        log(f"Критическая ошибка: {e}")

    finally:
        if driver:
            driver.quit()

    # ===================== SAVE =====================
    try:
        df = pd.DataFrame(results)
        out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
        os.makedirs(out_dir, exist_ok=True)
        df.to_csv(os.path.join(out_dir, "magnit_prices.csv"), index=False)
    except:
        pass

    # ===================== OUTPUT =====================
    sys.stdout.write(json.dumps(results, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()