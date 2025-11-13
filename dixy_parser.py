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

CHROMEDRIVER_PATH = r"C:\Users\KN\Tools\chromedriver.exe"

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
    "Чай Greenfield Golden Ceylon 200г",
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

# Selenium
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)

for product in products:
    name_only, unit_default = split_name_unit(product)
    encoded_query = urllib.parse.quote(product)
    url = f"https://dixy.ru/catalog/?q={encoded_query}"
    driver.get(url)
    time.sleep(2)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.catalog-item"))
        )

        cards = driver.find_elements(By.CSS_SELECTOR, "div.catalog-item")
        selected_card = None
        max_score = 0

        for card in cards:
            try:
                title_elem = card.find_element(By.CSS_SELECTOR, "div.card__info > p.card__title")
                title_text = title_elem.text.strip().lower()
                score = fuzz.token_sort_ratio(name_only.lower(), title_text)
                if score > max_score:
                    max_score = score
                    selected_card = card
            except:
                continue

        if selected_card and max_score > 50:
            # Цена
            try:
                price_elem = selected_card.find_element(By.CSS_SELECTOR, "div.card__price-num")
                main_price = re.search(r'\d+', price_elem.text).group()
                frac_elem = price_elem.find_element(By.TAG_NAME, "span")
                frac_price = frac_elem.text.strip()
                price = f"{main_price},{frac_price} ₽"
            except:
                price = None

            # Единица
            try:
                unit_elem = selected_card.find_element(By.CSS_SELECTOR, "span.catalog-item__measure")
                unit_from_site = unit_elem.text.strip() if unit_elem else unit_default or "1000 гр"
            except:
                unit_from_site = unit_default or "1000 гр"

            results.append({
                "store": "Дикси",
                "product": product,
                "unit": unit_from_site,
                "price": price,
                "date": today
            })
            print(f"✅ {name_only} — {price} — {unit_from_site} (score: {max_score})")
        else:
            print(f"⚠️ Дикси — {name_only} — товар не найден")
            results.append({
                "store": "Дикси",
                "product": product,
                "unit": unit_default or "1000 гр",
                "price": None,
                "date": today
            })

    except Exception as e:
        print(f"⚠️ Дикси — {name_only} — ошибка: {e}")
        results.append({
            "store": "Дикси",
            "product": product,
            "unit": unit_default or "1000 гр",
            "price": None,
            "date": today
        })

    time.sleep(2)

driver.quit()

# CSV
df = pd.DataFrame(results)
df.to_csv("dixy_prices.csv", index=False, encoding="utf-8-sig")
print(f"💾 Сохранено {len(df)} записей в dixy_prices.csv")
