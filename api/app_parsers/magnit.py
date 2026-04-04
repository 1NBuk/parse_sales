import time
import os
import sys
import random
import re
import urllib.parse
from datetime import datetime
import json
import warnings
import logging

warnings.filterwarnings('ignore')
os.environ['WDM_LOG'] = '0'
os.environ['WDM_PRINT'] = '0'

logging.getLogger('selenium').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('webdriver_manager').setLevel(logging.ERROR)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)

original_stdout = sys.stdout
sys.stdout = sys.stderr

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

sys.stdout = original_stdout

import pandas as pd
from rapidfuzz import fuzz
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

try:
    input_data = sys.stdin.read()
    if input_data:
        PRODUCTS = json.loads(input_data)
    else:
        PRODUCTS = []
    print(f"Получено продуктов: {len(PRODUCTS)}", file=sys.stderr)
except Exception as e:
    PRODUCTS = []
    print(f"Ошибка чтения: {e}", file=sys.stderr)

if not PRODUCTS:
    PRODUCTS = [
        "Яйцо Окское С1",
        "Батон Коломенский Нарезной",
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

TARGET_ADDRESS = "Панфилова 2"


def safe_get(driver, url):
    driver.get(url)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )


def normalize_query(text):
    return re.sub(r"\d+(\.\d+)?\s?(г|кг|мл|л|шт)", "", text, flags=re.I).strip()


def extract_unit(text):
    m = re.search(r"\d+\s?(г|кг|мл|л|шт)", text, re.I)
    return m.group(0) if m else ""


def scroll_all(driver):
    last = 0
    while True:
        height = driver.execute_script("return document.body.scrollHeight")
        if height == last:
            break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        last = height


def open_shop_bar(driver):
    bar = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "div.pl-shop-select-bar[data-test-id='map-button']")
        )
    )
    driver.execute_script("arguments[0].click();", bar)
    time.sleep(1.5)


def click_choose_store_screen(driver):
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[text()='Выберите магазин']]")
            )
        )
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(1.5)
    except TimeoutException:
        pass


def input_address_and_select(driver, address):
    address_input = WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located(
            (By.XPATH, "//input[@placeholder='Адрес магазина']")
        )
    )

    address_input.clear()
    address_input.send_keys(address)
    time.sleep(2)

    choose_btn = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[.//span[normalize-space()='Выбрать']]")
        )
    )

    driver.execute_script("arguments[0].click();", choose_btn)
    time.sleep(3)

    print(f"Магазин выбран по адресу: {address}", file=sys.stderr)


def ensure_store_selected(driver, address):
    print("Выбираем магазин", file=sys.stderr)
    open_shop_bar(driver)
    click_choose_store_screen(driver)
    input_address_and_select(driver, address)


def parse_card(card, default_unit):
    try:
        title = card.find_element(
            By.CSS_SELECTOR,
            ".unit-catalog-product-preview-title"
        ).text.strip()
    except:
        return None

    try:
        price_text = card.text
        price_match = re.search(r"(\d+[,.]?\d*)", price_text)
        if price_match:
            price = float(price_match.group(0).replace(",", "."))
        else:
            price = None
    except:
        price = None

    unit = extract_unit(title) or default_unit or "1 шт"
    return title, price, unit


def main():
    if not PRODUCTS:
        sys.stdout.write(json.dumps([], ensure_ascii=False))
        return

    results = []
    today = datetime.today().strftime("%Y-%m-%d")
    driver = None

    try:
        driver = create_driver(use_uc=True)
        safe_get(driver, "https://magnit.ru/")
        ensure_store_selected(driver, TARGET_ADDRESS)

        for product in PRODUCTS:
            product_clean = product.strip().strip('"').strip("'").strip()
            product_clean = re.sub(r'^["\']+|["\']+$', '', product_clean)
            if product_clean.endswith(','):
                product_clean = product_clean[:-1]

            print(f"Ищем: {product_clean}", file=sys.stderr)

            query = normalize_query(product_clean)
            default_unit = extract_unit(product_clean)

            url = f"https://magnit.ru/search/?term={urllib.parse.quote(query)}"
            safe_get(driver, url)
            time.sleep(2)
            scroll_all(driver)

            cards = driver.find_elements(
                By.CSS_SELECTOR,
                ".unit-catalog-product-preview"
            )

            print(f"Найдено карточек: {len(cards)}", file=sys.stderr)

            best = None
            best_score = 0

            for idx, card in enumerate(cards):
                parsed = parse_card(card, default_unit)
                if not parsed:
                    continue

                title, price, unit = parsed
                if title:
                    score = fuzz.token_sort_ratio(query.lower(), title.lower())
                    print(f"  Карточка {idx}: {title[:50]}... score={score}", file=sys.stderr)
                    if score > best_score:
                        best_score = score
                        best = (title, price, unit)

            if best and best_score >= 55:
                title, price, unit = best
                print(f"{product_clean} -> {price} ({title})", file=sys.stderr)
                results.append({
                    "store": "Магнит",
                    "product": product_clean,
                    "unit": unit,
                    "price": price,
                    "date": today
                })
            else:
                print(f"{product_clean} — не найден (score={best_score})", file=sys.stderr)
                results.append({
                    "store": "Магнит",
                    "product": product_clean,
                    "unit": default_unit or "1 шт",
                    "price": None,
                    "date": today
                })

            time.sleep(1 + random.random())

    except Exception as e:
        print(f"Критическая ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    try:
        df = pd.DataFrame(results)
        out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "magnit_prices.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Сохранено {len(results)} записей в {path}", file=sys.stderr)
        found_count = df[df['price'].notna()].shape[0]
        print(f"Найдено цен: {found_count} из {len(df)}", file=sys.stderr)
    except Exception as e:
        print(f"Ошибка сохранения: {e}", file=sys.stderr)

    json_output = json.dumps(results, ensure_ascii=False)
    sys.stdout.write(json_output)
    sys.stdout.flush()


if __name__ == "__main__":
    main()