import time
import pandas as pd
from datetime import datetime
import re
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz

# Путь к chromedriver
CHROMEDRIVER_PATH = r"C:\Users\User\Tools\chromedriver.exe"

products = [
    "Яйцо куриное Окское отборное С0 10шт",
    "Батон Коломенский Нарезной 200г",
    "Молоко Простоквашино отборное пастеризованное 3.4-4.5%",
    "Сахар песок белый 1кг",
    "Соль пищевая 1кг",
    "Крупа гречневая ядрица 900г",
    "Масло Олейна подсолнечное 1л",
    "Масло Брест-Литовск сливочное 82,5% 180г",
    "Бедро куриное Петелинка",
    "Чай Greenfield Golden Ceylon 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь",
    "Капуста белокочанная",
    "Яблоки"
]

results = []
today = datetime.today().strftime("%Y-%m-%d")


def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        unit = match.group(1)
        name = product.replace(unit, "").strip()
    else:
        unit = ""
        name = product
    return name, unit


# настройки Selenium
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")

service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)


for product in products:

    name_only, unit_default = split_name_unit(product)
    encoded = urllib.parse.quote(product)
    url = f"https://www.auchan.ru/product-search/?q={encoded}"

    print(f"🔎 Поиск: {product}")

    driver.get(url)
    time.sleep(2)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.digi-product"))
        )

        cards = driver.find_elements(By.CSS_SELECTOR, "div.digi-product")

        selected_card = None
        max_score = 0

        for card in cards:
            try:
                title_elem = card.find_element(By.CSS_SELECTOR, "a.digi-product__label")
                title_text = title_elem.text.strip()

                score = fuzz.token_sort_ratio(name_only.lower(), title_text.lower())

                if score > max_score:
                    max_score = score
                    selected_card = card

            except:
                continue

        if not selected_card or max_score < 40:
            print(f"⚠️ Ашан — {name_only} — товар не найден")
            results.append({
                "store": "Ашан",
                "product": product,
                "unit": unit_default,
                "price": None,
                "date": today
            })
            continue

        # --- цена ---
        try:
            price_elem = selected_card.find_element(
                By.CSS_SELECTOR,
                "span.digi-product-price-variant_actual"
            )

            raw_price = price_elem.text.strip().replace("\n", " ")

            # удаляем валюту внутри текста
            price = raw_price.replace("₽", "").strip() + " ₽"

        except Exception as e:
            print("⚠️ Ошибка цены:", e)
            price = None

        # --- единица измерения ---
        try:
            unit = unit_default if unit_default else ""
        except:
            unit = unit_default

        # Сохранение
        results.append({
            "store": "Ашан",
            "product": product,
            "unit": unit,
            "price": price,
            "date": today
        })

        print(f"✅ {name_only} — {price} (score={max_score})")

    except Exception as e:
        print(f"⚠️ Ашан — {name_only} — ошибка: {e}")

        results.append({
            "store": "Ашан",
            "product": product,
            "unit": unit_default,
            "price": None,
            "date": today
        })


driver.quit()

df = pd.DataFrame(results)
df.to_csv("auchan_prices.csv", index=False, encoding="utf-8-sig")
print(f"💾 Сохранено {len(df)} записей в auchan_prices.csv")
