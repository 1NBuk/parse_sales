import sys
import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)
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

if len(sys.argv) > 1:
    try:
        products = json.loads(sys.argv[1])  # ожидаем JSON-строку
    except:
        products = [sys.argv[1]]
else:
    products = [
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
    """
    Возвращает список карточек одного из двух типов
    """
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
    try:
        if card_type == "div.EProductSnippet2":
            # Старый тип
            title_el = card.find_element(By.CSS_SELECTOR, ".EProductSnippet2-Title")
            product_name = js_text(driver, title_el)

            price_el = card.find_element(By.CSS_SELECTOR, ".EPrice-Value")
            price = js_text(driver, price_el)

            store_el = card.find_element(By.CSS_SELECTOR, ".EShopName")
            store = js_text(driver, store_el)

        else:
            # Новый тип
            title_el = card.find_element(By.CSS_SELECTOR, ".EShopItem-Title")
            product_name = js_text(driver, title_el)

            price_el = card.find_element(By.CSS_SELECTOR, ".EPrice-Value")
            price = js_text(driver, price_el)

            store_el = card.find_element(By.CSS_SELECTOR, ".EShopItem-ShopName")
            store = js_text(driver, store_el)

        unit = extract_unit(product_name)
        return store, product_name, unit, price
    except Exception:
        return None, None, None, None

# --------------------------------------------------
def main():
    driver = create_driver()
    wait = WebDriverWait(driver, MAX_WAIT)
    today = datetime.today().strftime("%Y-%m-%d")
    results = []

    try:
        for query in products:
            print(f"Поиск: {query}")
            url = BASE_URL.format(query=quote_plus(query))
            driver.get(url)
            pause(1.5, 2.5)
            smooth_scroll(driver)
            pause(1.0, 2.0)

            cards, card_type = find_cards(driver, wait)

            if not cards:
                print(f"Карточки не найдены для {query}")
                results.append({"store": None, "product": query, "unit": None, "price": None, "date": today})
                continue

            print(f"Найдено карточек: {len(cards)} (тип: {card_type})")

            # Обработка карточек
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
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["store", "product", "unit", "price", "date"])
        writer.writeheader()
        writer.writerows(results)

    print(f"Сохранено записей: {len(results)}")
    print(f"Файл: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
