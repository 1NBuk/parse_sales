import time
import pandas as pd
import re
import urllib.parse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from rapidfuzz import fuzz

CHROMEDRIVER_PATH = r"C:\Users\User\Tools\chromedriver.exe"

products = [
    "Яйцо куриное Окское отборное С0 10шт",
    "Батон Коломенский Нарезной 200г",
    "Молоко Простоквашино отборное пастеризованное 3.4-4.5%",
    "Сахар кусковой белый 1кг",
    "Соль пищевая 1кг",
    "Крупа гречневая Мистраль 900г",
    "Масло Олейна подсолнечное 1л",
    "Масло Брест-Литовск сливочное 82,5% 180г",
    "Филе грудки цыпленка Петелинка",
    "Чай Greenfield Kenyan Sunrise чёрный байховый 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь отечественная",
    "Капуста белокочанная",
    "Яблоки сезонные"
]

results = []

def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        unit = match.group(1)
        name = product.replace(unit, "").strip()
    else:
        unit = ""
        name = product
    return name, unit

# Получаем текущую дату
today = datetime.today().strftime("%Y-%m-%d")

# ===== Перекресток =====
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)

for product in products:
    name_only, unit_default = split_name_unit(product)
    encoded_query = urllib.parse.quote(name_only)
    url = f"https://www.perekrestok.ru/cat/search?search={encoded_query}"
    driver.get(url)

    try:
        cards = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".product-card"))
        )

        selected_card = None
        max_score = 0
        price = None
        unit_from_site = unit_default or "1000 гр"

        # Проходим по всем карточкам и выбираем по максимальному score
        for card in cards:
            try:
                title_elem = card.find_element(By.CSS_SELECTOR, ".product-card__title")
                title_text = title_elem.text.strip().lower()
                score = fuzz.token_sort_ratio(name_only.lower(), title_text)

                if score > max_score:
                    max_score = score
                    selected_card = card
            except:
                continue

        if selected_card and max_score > 50:  # фильтр по минимальному сходству
            # Получаем цену
            for selector in [".price-new", ".product-card-price__current", ".product-card-price__discount"]:
                try:
                    elem = selected_card.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    if text:
                        price = text.replace("Цена", "").strip()
                        break
                except:
                    continue

            # Получаем unit
            try:
                unit_elem = selected_card.find_element(By.CSS_SELECTOR, ".product-card__size")
                if unit_elem.text.strip():
                    unit_from_site = unit_elem.text.strip()
            except:
                pass

            if not unit_from_site:
                unit_from_site = "1000 гр"

            print(f"Перекресток — {name_only} — {price} — {unit_from_site} (score: {max_score})")

        else:
            print(f"Перекресток — {name_only} — товар не найден")
            price = None

        results.append({
            "store": "Перекресток",
            "product": name_only,
            "unit": unit_from_site,
            "price": price,
            "date": today
        })

    except:
        print(f"Перекресток — {name_only} — ошибка при поиске")
        results.append({
            "store": "Перекресток",
            "product": name_only,
            "unit": unit_default or "1000 гр",
            "price": None,
            "date": today
        })

    time.sleep(1)

driver.quit()

# ===== Сохраняем CSV =====
df = pd.DataFrame(results)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
os.makedirs(BASE_DIR, exist_ok=True)
file_path = os.path.join(BASE_DIR, "perekrestok_prices.csv")
df.to_csv(file_path, index=False, encoding="utf-8-sig")
print(f"Сохранено {len(df)} записей в {file_path}")
