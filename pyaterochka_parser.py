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

# Настройки Selenium
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)

for product in products:
    name_only, unit_default = split_name_unit(product)
    encoded_query = urllib.parse.quote(product)
    url = f"https://5ka.ru/search/?text={encoded_query}"

    time.sleep(2)  # пауза перед загрузкой страницы
    driver.get(url)
    time.sleep(2)  # пауза после загрузки страницы

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.css-i9gxme"))
        )

        cards = driver.find_elements(By.CSS_SELECTOR, "div.css-i9gxme")
        selected_card = None
        max_score = 0

        # Выбираем карточку с наибольшим сходством названия
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

        if selected_card and max_score > 50:
            # Ждем появления цены внутри выбранной карточки
            price = None
            try:
                WebDriverWait(selected_card, 5).until(
                    lambda x: x.find_elements(By.CSS_SELECTOR, "div.css-1gnr8ln span")
                )
                spans = selected_card.find_elements(By.CSS_SELECTOR, "div.css-1gnr8ln span")
                if len(spans) >= 2 and spans[0].text.strip().isdigit():
                    price = f"{spans[0].text.strip()},{spans[1].text.strip()} ₽"
            except:
                price = None

            # Получаем единицу измерения
            try:
                unit_elem = selected_card.find_element(By.CSS_SELECTOR, "div.css-p5esxm > p[type='caption']")
                unit_from_site = unit_elem.text.strip() if unit_elem and unit_elem.text.strip() else unit_default or "1000 гр"
            except:
                unit_from_site = unit_default or "1000 гр"

            results.append({
                "store": "Пятерочка",
                "product": product,
                "unit": unit_from_site,
                "price": price,
                "date": today
            })

            print(f"✅ {name_only} — {price} — {unit_from_site} (score: {max_score})")

        else:
            print(f"⚠️ Пятерочка — {name_only} — товар не найден")
            results.append({
                "store": "Пятерочка",
                "product": product,
                "unit": unit_default or "1000 гр",
                "price": None,
                "date": today
            })

    except Exception as e:
        print(f"⚠️ Пятерочка — {name_only} — ошибка: {e}")
        results.append({
            "store": "Пятерочка",
            "product": product,
            "unit": unit_default or "1000 гр",
            "price": None,
            "date": today
        })

    #time.sleep(1)  # пауза после обработки запроса

driver.quit()

df = pd.DataFrame(results)
df.to_csv("pyaterochka_prices.csv", index=False, encoding="utf-8-sig")
print(f"💾 Сохранено {len(df)} записей в pyaterochka_prices.csv")
