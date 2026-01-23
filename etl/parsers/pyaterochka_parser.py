import time
import os
import re
import urllib.parse
import pandas as pd
from datetime import datetime
from rapidfuzz import fuzz

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================= НАСТРОЙКИ =================

CHROMEDRIVER_PATH = r"C:\Users\User\Tools\chromedriver.exe"

PRODUCTS = [
    "Яйцо куриное Окское отборное С0 10шт",
    "Батон Коломенский Нарезной 200г",
    "Молоко Простоквашино отборное пастеризованное 3.4-4.5%",
    "Сахар кусковой белый 1кг",
    "Соль пищевая 1кг",
    "Крупа гречневая Мистраль 900г",
    "Масло Олейна подсолнечное 1л",
    "Масло Брест-Литовск сливочное 82,5% 180г",
    "Филе грудки цыпленка Петелинка",
    "Чай Greenfield Золотой Цейлон 100г",
    "Картофель отечественный",
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
        unit = match.group(1)
        name = product.replace(unit, "").strip()
    else:
        unit = ""
        name = product
    return name, unit


def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def warmup_site(driver):
    driver.get("https://5ka.ru")
    time.sleep(5)


def parse_product(driver, product, is_first=False):
    name_only, unit_default = split_name_unit(product)
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
                WebDriverWait(selected_card, 5).until(
                    lambda x: x.find_elements(By.CSS_SELECTOR, "div.css-1gnr8ln span")
                )
                spans = selected_card.find_elements(By.CSS_SELECTOR, "div.css-1gnr8ln span")
                if len(spans) >= 2:
                    price = f"{spans[0].text.strip()},{spans[1].text.strip()} ₽"
            except:
                pass

            # Единица измерения
            try:
                unit_elem = selected_card.find_element(
                    By.CSS_SELECTOR, "div.css-p5esxm > p[type='caption']"
                )
                unit = unit_elem.text.strip() if unit_elem.text.strip() else unit_default
            except:
                unit = unit_default or "1000 гр"

            print(f"{name_only} — {price} — {unit} (score: {max_score})")

            return {
                "store": "Пятерочка",
                "product": product,
                "unit": unit,
                "price": price,
                "date": today
            }

        except:
            continue

    print(f"Пятерочка — {name_only} — товар не найден")
    return {
        "store": "Пятерочка",
        "product": product,
        "unit": unit_default or "1000 гр",
        "price": None,
        "date": today
    }


# ================= ОСНОВНОЙ КОД =================

today = datetime.today().strftime("%Y-%m-%d")
results = []

driver = setup_driver()
time.sleep(5)
warmup_site(driver)

for idx, product in enumerate(PRODUCTS):
    result = parse_product(driver, product, is_first=(idx == 0))
    results.append(result)
    time.sleep(1)

driver.quit()

df = pd.DataFrame(results)
df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print(f"\nСохранено {len(df)} записей в {OUTPUT_FILE}")
