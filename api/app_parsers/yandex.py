import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)

# Принудительно UTF-8 для stdout (важно на Windows с cp1251)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import time
import random
import re
import csv
from datetime import datetime
from urllib.parse import quote_plus
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from rapidfuzz import fuzz

# --------------------------------------------------
BASE_URL = "https://yandex.ru/search/?text={query}&lr=120373&products_mode=1"
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "raw", "yandex_products_prices.csv")

MIN_FUZZ_SCORE = 55
MAX_WAIT = 30

# --------------------------------------------------
# Читаем продукты: приложение передаёт JSON через stdin,
# при прямом запуске используем sys.argv или дефолтный список
# --------------------------------------------------
def load_products():
    # 1. Проверяем stdin (запуск из приложения)
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read().strip()
            if raw:
                return json.loads(raw)
        except Exception:
            pass

    # 2. Проверяем аргументы командной строки (ручной запуск)
    if len(sys.argv) > 1:
        try:
            return json.loads(sys.argv[1])
        except Exception:
            return [sys.argv[1]]

    # 3. Дефолтный список для отладки
    return [
        "Яйцо куриное Окское С1 10шт",
        "Батон Коломенский Нарезной 200г",
        "Молоко Простоквашино отборное пастеризованное 3.4-4.5%",
        "Сахар кусковой белый 1кг",
        "Соль пищевая 1кг",
        "Крупа гречневая Мистраль 900г",
        "Масло Олейна подсолнечное 1л",
        "Масло Брест-Литовск сливочное 82,5% 180г",
        "Филе грудки цыпленка Петелинка",
        "Чай Greenfield Golden Ceylon 100г",
        "Картофель белый, вес",
        "Лук репчатый",
        "Социальный товар Морковь",
        "Капуста белокочанная",
        "Яблоки Гала"
    ]


def pause(a=0.6, b=1.6):
    time.sleep(random.uniform(a, b))

def log(msg):
    print(msg, file=sys.stderr)

def js_text(driver, el):
    return driver.execute_script("return arguments[0].textContent || '';", el).strip()

def extract_unit(text):
    m = re.search(r"(\d+\s?(?:шт|г|кг|мл|л))", text.lower())
    return m.group(1) if m else ""

def smooth_scroll(driver):
    height = driver.execute_script("return document.body.scrollHeight")
    steps = random.randint(5, 8)
    for i in range(1, steps + 1):
        driver.execute_script(f"window.scrollTo(0, {int(height * i / steps)});")
        pause(0.4, 0.9)

def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(options=options)

# --------------------------------------------------
def find_cards(driver, wait):
    selectors = [
        "div.EProductSnippet2",  # старый тип
        "li.EShopItem"           # новый тип
    ]
    for sel in selectors:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            cards = driver.find_elements(By.CSS_SELECTOR, sel)
            if cards:
                return cards, sel
        except TimeoutException:
            continue
    return [], None

# --------------------------------------------------
def extract_data(card, card_type, driver):
    """Возвращает (store, product_name, unit, price).
    store берётся из карточки — название магазина на Яндекс.Маркете.
    """
    try:
        if card_type == "div.EProductSnippet2":
            title_el = card.find_element(By.CSS_SELECTOR, ".EProductSnippet2-Title")
            product_name = js_text(driver, title_el)

            price_el = card.find_element(By.CSS_SELECTOR, ".EPrice-Value")
            price = js_text(driver, price_el)

            # Название магазина из карточки; если не нашли — "Яндекс.Маркет"
            try:
                store_el = card.find_element(By.CSS_SELECTOR, ".EShopName")
                store = js_text(driver, store_el) or "Яндекс.Маркет"
            except Exception:
                store = "Яндекс.Маркет"

        else:
            title_el = card.find_element(By.CSS_SELECTOR, ".EShopItem-Title")
            product_name = js_text(driver, title_el)

            price_el = card.find_element(By.CSS_SELECTOR, ".EPrice-Value")
            price = js_text(driver, price_el)

            try:
                store_el = card.find_element(By.CSS_SELECTOR, ".EShopItem-ShopName")
                store = js_text(driver, store_el) or "Яндекс.Маркет"
            except Exception:
                store = "Яндекс.Маркет"

        unit = extract_unit(product_name)
        return store, product_name, unit, price
    except Exception:
        return None, None, None, None

# --------------------------------------------------
def main():
    products = load_products()

    driver = create_driver()
    wait = WebDriverWait(driver, MAX_WAIT)
    today = datetime.today().strftime("%Y-%m-%d")
    results = []

    try:
        for query in products:
            log(f"Поиск: {query}")
            url = BASE_URL.format(query=quote_plus(query))
            driver.get(url)
            pause(1.5, 2.5)
            smooth_scroll(driver)
            pause(1.0, 2.0)

            cards, card_type = find_cards(driver, wait)

            if not cards:
                log(f"Карточки не найдены для {query}")
                results.append({
                    "store": "Яндекс.Маркет",
                    "product": query,
                    "unit": None,
                    "price": None,
                    "date": today
                })
                continue

            log(f"Найдено карточек: {len(cards)} (тип: {card_type})")

            for card in cards:
                pause(0.3, 0.8)
                store, product_name, unit, price = extract_data(card, card_type, driver)
                if not product_name:
                    continue
                score = fuzz.token_set_ratio(query.lower(), product_name.lower())
                if score < MIN_FUZZ_SCORE:
                    continue
                results.append({
                    "store": store,
                    "product": product_name,
                    "unit": unit,
                    "price": price,
                    "date": today
                })

            pause(2.0, 3.0)

    finally:
        driver.quit()

    # --------------------------------------------------
    # Сохраняем CSV (для ETL-пайплайна)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["store", "product", "unit", "price", "date"])
        writer.writeheader()
        writer.writerows(results)

    log(f"Сохранено записей: {len(results)}")
    log(f"Файл: {OUTPUT_PATH}")

    # Выводим JSON в stdout — именно это читает приложение
    sys.stdout.write(json.dumps(results, ensure_ascii=True))
    sys.stdout.flush()


if __name__ == "__main__":
    main()