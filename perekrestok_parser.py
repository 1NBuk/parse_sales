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
        card = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-card"))
        )

        # Получаем цену
        price = None
        for selector in [".price-new", ".product-card-price__current", ".product-card-price__discount"]:
            try:
                elem = card.find_element(By.CSS_SELECTOR, selector)
                text = elem.text.strip()
                if text:
                    price = text.replace("Цена", "").strip()
                    break
            except:
                continue

        # Получаем unit
        unit_from_site = unit_default
        try:
            unit_elem = card.find_element(By.CSS_SELECTOR, ".product-card__size")
            if unit_elem.text.strip():
                unit_from_site = unit_elem.text.strip()
        except:
            pass

        # Если unit пустой, ставим 1000 гр
        if not unit_from_site:
            unit_from_site = "1000 гр"

        if price:
            print(f"✅ Перекресток — {name_only} — {price} — {unit_from_site}")
        else:
            print(f"⚠️ Перекресток — {name_only} — цена не найдена — {unit_from_site}")

        results.append({
            "store": "Перекресток",
            "product": name_only,
            "unit": unit_from_site,
            "price": price,
            "date": today
        })

    except:
        print(f"⚠️ Перекресток — {name_only} — товар не найден")
        unit_final = unit_default if unit_default else "1000 гр"
        results.append({
            "store": "Перекресток",
            "product": name_only,
            "unit": unit_final,
            "price": None,
            "date": today
        })

    time.sleep(1)

driver.quit()

# ===== Сохраняем CSV =====
df = pd.DataFrame(results)
df.to_csv("perekrestok_prices.csv", index=False, encoding="utf-8-sig")
print(f"💾 Сохранено {len(df)} записей в perekrestok_prices.csv")
