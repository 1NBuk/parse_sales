import sys
import os
import json
import time
import random
import re
import csv
from datetime import datetime
from urllib.parse import quote_plus
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from rapidfuzz import fuzz

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "raw", "yandex_products_prices.csv")
BASE_URL = "https://yandex.ru/search/?text={query}&lr=120373&products_mode=1"

MIN_FUZZ_SCORE = 40
MAX_WAIT = 30
MAX_CARDS = 50

try:
    input_data = sys.stdin.read()
    if input_data:
        products = json.loads(input_data)
    else:
        products = []
except Exception as e:
    products = []

if not products:
    if len(sys.argv) > 1:
        try:
            products = json.loads(sys.argv[1])
            if isinstance(products, str):
                products = [products]
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
            "Морковь",
            "Капуста белокочанная",
            "Яблоки сезонные"
        ]


def clean_text(text):
    if not text:
        return text
    text = re.sub(r'[\u2060\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e]', '', text)
    text = re.sub(r'[^\x00-\x7F]+', lambda m: m.group(0).encode('ascii', 'ignore').decode('ascii'), text)
    return text.strip()


def pause(a=0.5, b=1.5):
    time.sleep(random.uniform(a, b))


def clean_name(name):
    return name.strip().rstrip(',')


def extract_unit(text):
    m = re.search(r"(\d+\s?(шт|г|кг|мл|л))", text.lower())
    return m.group(1) if m else ""


def js_text(driver, el):
    return driver.execute_script("return arguments[0].textContent || '';", el).strip()


def smooth_scroll(driver):
    height = driver.execute_script("return document.body.scrollHeight")
    steps = random.randint(5, 8)
    for i in range(1, steps + 1):
        driver.execute_script(f"window.scrollTo(0, {int(height * i / steps)});")
        pause(0.3, 0.6)


def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(options=options)


def find_cards(driver, wait):
    selectors = ["div.EProductSnippet2", "li.EShopItem"]
    for sel in selectors:
        try:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, sel)))
            cards = driver.find_elements(By.CSS_SELECTOR, sel)
            if cards:
                return cards, sel
        except TimeoutException:
            continue
    return [], None


def extract_data(card, card_type, driver):
    try:
        if card_type == "div.EProductSnippet2":
            product_name = js_text(driver, card.find_element(By.CSS_SELECTOR, ".EProductSnippet2-Title"))
            price = js_text(driver, card.find_element(By.CSS_SELECTOR, ".EPrice-Value"))
            store = js_text(driver, card.find_element(By.CSS_SELECTOR, ".EShopName"))
        else:
            product_name = js_text(driver, card.find_element(By.CSS_SELECTOR, ".EShopItem-Title"))
            price = js_text(driver, card.find_element(By.CSS_SELECTOR, ".EPrice-Value"))
            store = js_text(driver, card.find_element(By.CSS_SELECTOR, ".EShopItem-ShopName"))

        product_name = clean_text(product_name)
        store = clean_text(store)
        unit = extract_unit(product_name)
        price_val = float(re.search(r"(\d+[.,]?\d*)", price).group(1).replace(",", ".")) if price else None
        return store, product_name, unit, price_val
    except:
        return None, None, None, None

def main():
    if not products:
        sys.stdout.write(json.dumps([], ensure_ascii=False))
        return

    driver = create_driver()
    wait = WebDriverWait(driver, MAX_WAIT)
    today = datetime.today().strftime("%Y-%m-%d")
    results = []

    print(f"Mode: {'single product' if len(products) == 1 else f'{len(products)} products'}", file=sys.stderr)
    print(f"Products to parse: {products}", file=sys.stderr)

    try:
        for query in products:
            query_clean = clean_name(query)
            print(f"Searching: {query_clean}", file=sys.stderr)
            url = BASE_URL.format(query=quote_plus(query_clean))
            driver.get(url)
            pause(1.5, 2.5)
            smooth_scroll(driver)
            pause(1.0, 2.0)

            cards, card_type = find_cards(driver, wait)

            if not cards:
                print(f"No cards found for {query_clean}", file=sys.stderr)
                results.append({"store": None, "product": query_clean, "unit": None, "price": None, "date": today})
                continue

            matches_for_product = 0
            # Цикл по всем карточкам без break
            for idx, card in enumerate(cards[:MAX_CARDS]):
                store, product_name, unit, price = extract_data(card, card_type, driver)
                if not product_name:
                    continue

                score = fuzz.token_set_ratio(query_clean.lower(), product_name.lower())
                if score >= MIN_FUZZ_SCORE:
                    results.append({
                        "store": store,
                        "product": product_name,
                        "unit": unit,
                        "price": price,
                        "date": today
                    })
                    matches_for_product += 1
                    print(
                        f"  Match {matches_for_product}: {product_name[:50]}... (price: {price}, store: {store}, score: {score}%)",
                        file=sys.stderr
                    )

                pause(0.1, 0.3)

            if matches_for_product == 0:
                print(f"  No matches found for {query_clean}", file=sys.stderr)
                results.append({"store": None, "product": query_clean, "unit": None, "price": None, "date": today})
            else:
                print(f"  Total matches for {query_clean}: {matches_for_product}", file=sys.stderr)

    except Exception as e:
        print(f"Critical error: {e}", file=sys.stderr)
    finally:
        driver.quit()

        if results:
            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
            with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["store", "product", "unit", "price", "date"])
                writer.writeheader()
                writer.writerows(results)
            print(f"Saved {len(results)} records to {OUTPUT_PATH}", file=sys.stderr)

        json_output = json.dumps(results, ensure_ascii=False)
        sys.stdout.buffer.write(json_output.encode('utf-8'))
        sys.stdout.flush()


if __name__ == "__main__":
    main()