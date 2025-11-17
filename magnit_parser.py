import time
import pandas as pd
import urllib.parse
import re
from datetime import datetime
from rapidfuzz import fuzz

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CHROMEDRIVER_PATH = r"C:\Users\User\Tools\chromedriver.exe"

products = [
    "Яйцо куриное Окское С0 10шт",
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

# Адрес для выбора
TARGET_ADDRESS = "г Москва, пр-кт Ленинградский, д 29 к 4"

def normalize_query(name):
    return re.sub(r"\d+(\.\d+)?\s?(г|кг|мл|л|шт)", "", name, flags=re.IGNORECASE).strip()

def extract_unit(name):
    m = re.search(r"(\d+\s?(г|кг|мл|л|шт))", name, re.IGNORECASE)
    return m.group(1) if m else ""

# Настройки Selenium
options = Options()
options.add_argument("--start-maximized")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)

results = []
today = datetime.today().strftime("%Y-%m-%d")

# --- Шаг 1: Выбираем адрес ---
driver.get("https://magnit.ru/")
time.sleep(2)

try:
    # Ждем кнопку "Выбрать" в модальном окне
    choose_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//span[text()='Выбрать']/ancestor::button"))
    )
    choose_btn.click()
    time.sleep(1)

    # Находим поле ввода адреса
    address_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input.pl-input-field"))
    )
    address_input.clear()
    address_input.send_keys(TARGET_ADDRESS)
    time.sleep(2)  # ждем появления подсказок

    # Выбираем нужный адрес из выпадающего списка
    address_option = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, f"//div[contains(@class,'shop-address') and contains(text(),'{TARGET_ADDRESS}')]"))
    )
    address_option.click()
    time.sleep(1)

    # Нажимаем кнопку "Выбрать" в списке адресов
    confirm_btn = driver.find_element(By.XPATH, "//button[contains(@class,'pl-yamap__balloon__submit')]")
    confirm_btn.click()
    time.sleep(2)

except Exception as e:
    print(f"Ошибка при выборе адреса: {e}")

# --- Шаг 2: Парсим товары ---
for product in products:
    query = normalize_query(product)
    unit_default = extract_unit(product)
    encoded = urllib.parse.quote(query)
    url = f"https://magnit.ru/search/?term={encoded}"

    driver.get(url)
    time.sleep(2)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".unit-catalog-product-preview-text"))
        )

        cards = driver.find_elements(By.CSS_SELECTOR, ".unit-catalog-product-preview-text")
        best_card = None
        best_score = 0
        best_title = ""

        for card in cards:
            try:
                title_el = card.find_element(By.CSS_SELECTOR, ".unit-catalog-product-preview-title")
                title = title_el.text.strip()
                score = fuzz.token_sort_ratio(query.lower(), title.lower())
                if score > best_score:
                    best_score = score
                    best_card = card
                    best_title = title
            except:
                continue

        if best_card and best_score >= 60:
            try:
                price_el = best_card.find_element(By.CSS_SELECTOR, ".unit-catalog-product-preview-prices__regular")
                price_raw = price_el.text.strip()
                price = re.sub(r"[^\d,\.]", "", price_raw)
                if ',' not in price and '.' in price:
                    price = price.replace('.', ',')
            except:
                price = None

            try:
                unit_match = re.search(r"(\d+\s?(г|кг|мл|л|шт))", best_title)
                unit_from_site = unit_match.group(1) if unit_match else unit_default or "1000 гр"
            except:
                unit_from_site = unit_default or "1000 гр"

            results.append({
                "store": "Магнит",
                "product": product,
                "found_name": best_title,
                "price": price,
                "unit": unit_from_site,
                "date": today
            })
            print(f"✅ {product} → {price} ({best_title})")

        else:
            print(f"⚠️ Не найдено: {product}")
            results.append({
                "store": "Магнит",
                "product": product,
                "found_name": None,
                "price": None,
                "unit": unit_default,
                "date": today
            })

    except Exception as e:
        print(f"Ошибка ({product}): {e}")

    time.sleep(1)

driver.quit()

# --- Сохраняем CSV ---
df = pd.DataFrame(results)
df.to_csv("magnit_prices.csv", index=False, encoding="utf-8-sig")
print("\n💾 Готово: magnit_prices.csv")
