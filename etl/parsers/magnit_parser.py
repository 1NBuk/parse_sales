import time
import os
import sys
import random
import re
import urllib.parse
from datetime import datetime

import pandas as pd
from rapidfuzz import fuzz
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

sys.path.append(os.path.dirname(__file__))
from etl.driver_utils import create_driver


# ================= НАСТРОЙКИ =================

PRODUCTS = [
    "Яйцо Окское С1",
    "Батон Коломенский Нарезной",
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

TARGET_ADDRESS = "Панфилова 2"


# ================= УТИЛИТЫ =================

def safe_get(driver, url):
    driver.get(url)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )


def normalize_query(text):
    return re.sub(r"\d+(\.\d+)?\s?(г|кг|мл|л|шт)", "", text, flags=re.I).strip()


def extract_unit(text):
    m = re.search(r"\d+\s?(г|кг|мл|л|шт)", text, re.I)
    return m.group(0) if m else ""


def scroll_all(driver):
    last = 0
    while True:
        height = driver.execute_script("return document.body.scrollHeight")
        if height == last:
            break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        last = height


# ================= ВЫБОР МАГАЗИНА =================

def open_shop_bar(driver):
    bar = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "div.pl-shop-select-bar[data-test-id='map-button']")
        )
    )
    driver.execute_script("arguments[0].click();", bar)
    time.sleep(1.5)


def click_choose_store_screen(driver):
    """Экран 'Выберите магазин' с большой кнопкой"""
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[text()='Выберите магазин']]")
            )
        )
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(1.5)
    except TimeoutException:
        pass


def input_address_and_select(driver, address):
    """ГЛАВНОЕ: ввод именно в 'Адрес магазина' + кнопка 'Выбрать'"""

    # поле "Адрес магазина"
    address_input = WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located(
            (By.XPATH, "//input[@placeholder='Адрес магазина']")
        )
    )

    address_input.clear()
    address_input.send_keys(address)
    time.sleep(2)

    # кнопка "Выбрать" у первого магазина
    choose_btn = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[.//span[normalize-space()='Выбрать']]")
        )
    )

    driver.execute_script("arguments[0].click();", choose_btn)
    time.sleep(3)

    print(f"[✓] Магазин выбран по адресу: {address}")


def ensure_store_selected(driver, address):
    print("[i] Выбираем магазин")
    open_shop_bar(driver)
    click_choose_store_screen(driver)
    input_address_and_select(driver, address)


# ================= ПАРСИНГ =================

def parse_card(card, default_unit):
    try:
        title = card.find_element(
            By.CSS_SELECTOR,
            ".unit-catalog-product-preview-title"
        ).text.strip()
    except:
        return None

    try:
        price_text = card.text
        price = re.search(r"\d+[,.]?\d*", price_text).group(0).replace(".", ",")
    except:
        price = None

    unit = extract_unit(title) or default_unit or "1 шт"
    return title, price, unit


# ================= MAIN =================

def main():
    driver = create_driver(use_uc=True)
    today = datetime.today().strftime("%Y-%m-%d")
    results = []

    try:
        safe_get(driver, "https://magnit.ru/")
        ensure_store_selected(driver, TARGET_ADDRESS)

        for product in PRODUCTS:
            query = normalize_query(product)
            default_unit = extract_unit(product)

            url = f"https://magnit.ru/search/?term={urllib.parse.quote(query)}"
            safe_get(driver, url)
            time.sleep(2)
            scroll_all(driver)

            cards = driver.find_elements(
                By.CSS_SELECTOR,
                ".unit-catalog-product-preview"
            )

            best, best_score = None, 0

            for card in cards:
                parsed = parse_card(card, default_unit)
                if not parsed:
                    continue

                title, price, unit = parsed
                score = fuzz.token_sort_ratio(query.lower(), title.lower())

                if score > best_score:
                    best_score = score
                    best = (title, price, unit)

            if best and best_score >= 55:
                title, price, unit = best
                print(f"{product} → {price} ({title})")
            else:
                title = price = unit = None
                print(f"[!] {product} — не найден")

            results.append({
                "store": "Магнит",
                "product": product,
                "found_name": title,
                "price": price,
                "unit": unit,
                "date": today
            })

            time.sleep(1 + random.random())

    finally:
        driver.quit()

    df = pd.DataFrame(results)
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "magnit_prices.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")

    print(f"[OK] Сохранено: {path}")


if __name__ == "__main__":
    main()
