import sys
import os
import time
import random
import re
import json
import warnings
import logging
from datetime import datetime
from urllib.parse import quote_plus

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from rapidfuzz import fuzz

warnings.filterwarnings("ignore")
logging.getLogger("selenium").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("webdriver_manager").setLevel(logging.ERROR)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "raw", "dixy_prices.csv")

MIN_FUZZ_SCORE = 50
MAX_WAIT = 20

# ------------------- Получаем продукты -------------------
try:
    input_data = sys.stdin.read()
    if input_data:
        PRODUCTS = json.loads(input_data)
    else:
        PRODUCTS = []
except Exception as e:
    PRODUCTS = []
    print(f"Ошибка чтения входных данных: {e}", file=sys.stderr)

if not PRODUCTS:
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

today = datetime.today().strftime("%Y-%m-%d")
results = []

# ------------------- Утилиты -------------------
def pause(a=0.5, b=1.5):
    time.sleep(random.uniform(a, b))

def clean_name(product):
    name = product.strip()
    name = re.sub(r'^["\']+|["\']+$', '', name)
    if name.endswith(','):
        name = name[:-1]
    return name.strip()

def extract_unit(text):
    m = re.search(r"(\d+\s?(?:шт|г|кг|мл|л))", text.lower())
    return m.group(1) if m else "1 кг"

def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    return webdriver.Chrome(options=options)

def parse_price(card):
    try:
        price_el = card.find_element(By.CSS_SELECTOR, "[class*='price']")
        m = re.search(r"(\d+[.,]?\d*)", price_el.text)
        if m:
            return float(m.group(1).replace(",", "."))
    except:
        return None

# ------------------- Основная логика -------------------
def main():
    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, MAX_WAIT)

        # Сначала открываем главную страницу, чтобы прогрузились скрипты
        print("Загрузка главной страницы Дикси...", file=sys.stderr)
        driver.get("https://dixy.ru")
        pause(3, 5)

        for product in PRODUCTS:
            product_clean = clean_name(product)
            search_url = f"https://dixy.ru/catalog/?q={quote_plus(product_clean)}"
            print(f"\nИщем: {product_clean}", file=sys.stderr)
            print(f"URL: {search_url}", file=sys.stderr)

            driver.get(search_url)
            pause(2, 4)

            try:
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article")))
                cards = driver.find_elements(By.CSS_SELECTOR, "article")
                print(f"Найдено карточек: {len(cards)}", file=sys.stderr)
            except TimeoutException:
                print(f"Товары не найдены для {product_clean}", file=sys.stderr)
                results.append({
                    "store": "Дикси",
                    "product": product_clean,
                    "unit": "1 кг",
                    "price": None,
                    "date": today
                })
                continue

            best_score = -1
            best_card = None
            for idx, card in enumerate(cards):
                try:
                    title = card.text.split("\n")[0]
                    score = fuzz.token_sort_ratio(product_clean.lower(), title.lower())
                    print(f"  Карточка {idx}: {title[:50]}... score={score}", file=sys.stderr)
                    if score > best_score:
                        best_score = score
                        best_card = card
                except:
                    continue

            if not best_card or best_score < MIN_FUZZ_SCORE:
                print(f"Дикси — {product_clean} — товар не найден", file=sys.stderr)
                results.append({
                    "store": "Дикси",
                    "product": product_clean,
                    "unit": "1 кг",
                    "price": None,
                    "date": today
                })
                continue

            price = parse_price(best_card)
            unit_match = re.search(r"(\d+\s?(г|кг|мл|л|шт))", best_card.text)
            unit = unit_match.group(1) if unit_match else "1 кг"

            print(f"Дикси — {product_clean} — {price} ₽ — {unit} (score={best_score})", file=sys.stderr)
            results.append({
                "store": "Дикси",
                "product": product_clean,
                "unit": unit,
                "price": price,
                "date": today
            })
            pause(1, 2)

    except Exception as e:
        import traceback
        print(f"Критическая ошибка: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    # ------------------- Сохраняем CSV с BOM -------------------
    try:
        df = pd.DataFrame(results)
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")  # BOM для Excel
        print(f"\nСохранено {len(results)} записей в {OUTPUT_PATH}", file=sys.stderr)
        found_count = df[df['price'].notna()].shape[0]
        print(f"Найдено цен: {found_count} из {len(df)}", file=sys.stderr)
    except Exception as e:
        print(f"Ошибка сохранения CSV: {e}", file=sys.stderr)

    # ------------------- Вывод JSON в stdout для Streamlit -------------------
    try:
        json_output = json.dumps(results, ensure_ascii=False)
        # Пишем как текстовую строку, без encode
        sys.stdout.write(json_output)
        sys.stdout.flush()
    except Exception as e:
        print(f"Ошибка вывода JSON: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()