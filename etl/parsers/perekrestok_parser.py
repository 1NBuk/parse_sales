import time
import pandas as pd
from datetime import datetime
import re
import os
import sys
import urllib.parse

# ----------------------
# driver_utils
# ----------------------
sys.path.append(os.path.dirname(__file__))

try:
    from etl.driver_utils import create_driver
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "driver_utils",
        os.path.join(os.path.dirname(__file__), "driver_utils.py")
    )
    driver_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver_utils)
    create_driver = driver_utils.create_driver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz

# ----------------------
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
    "Чай Greenfield Kenyan Sunrise 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь отечественная",
    "Капуста белокочанная",
    "Яблоки сезонные"
]

results = []
today = datetime.today().strftime("%Y-%m-%d")

# ----------------------
def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""  # если нет веса

# ----------------------
def extract_price(card, driver):
    selectors = [
        ".price-new",
        ".product-card-price__current",
        ".product-card-price__discount"
    ]
    for sel in selectors:
        try:
            elem = card.find_element(By.CSS_SELECTOR, sel)
            raw = elem.text.strip()
            m = re.search(r"(\d+[.,]?\d*)", raw)
            if m:
                return m.group(1).replace(",", ".") + " ₽"
        except:
            continue

    # fallback через JS
    try:
        js = driver.execute_script("""
            let el = arguments[0].querySelector(".price-new, .product-card-price__current, .product-card-price__discount");
            return el ? el.textContent : null;
        """, card)
        if js:
            m = re.search(r"(\d+[.,]?\d*)", js)
            if m:
                return m.group(1).replace(",", ".") + " ₽"
    except:
        pass

    return None

# ----------------------
def main():
    driver = create_driver(use_uc=True)

    try:
        for product in products:
            name_only, unit_default = split_name_unit(product)
            if not unit_default:
                unit_default = "1 кг"

            encoded_query = urllib.parse.quote(name_only)
            url = f"https://www.perekrestok.ru/cat/search?search={encoded_query}"

            try:
                driver.get(url)
                WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".product-card"))
                )
                time.sleep(1)

                cards = driver.find_elements(By.CSS_SELECTOR, ".product-card")

                best_index = None
                best_score = -1

                for idx in range(len(cards)):
                    # всегда берём свежий элемент, чтобы избежать stale
                    cards = driver.find_elements(By.CSS_SELECTOR, ".product-card")
                    card = cards[idx]

                    title = ""
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, ".product-card__title")
                        title = title_elem.text.strip()
                    except:
                        continue

                    score = fuzz.token_sort_ratio(name_only.lower(), title.lower())
                    if score > best_score:
                        best_score = score
                        best_index = idx

                if best_index is None or best_score < 50:
                    print(f"Перекресток — {name_only} — товар не найден (score={best_score})")
                    results.append({
                        "store": "Перекресток",
                        "product": name_only,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                # берём лучшую карточку
                cards = driver.find_elements(By.CSS_SELECTOR, ".product-card")
                best_card = cards[best_index]

                price = extract_price(best_card, driver)

                # unit
                card_text = best_card.text
                match_unit = re.search(r"(\d+\s?(г|кг|мл|л|шт))", card_text)
                unit_site = match_unit.group(1) if match_unit else unit_default

                results.append({
                    "store": "Перекресток",
                    "product": name_only,
                    "unit": unit_site,
                    "price": price,
                    "date": today
                })

                print(f"Перекресток — {name_only} — {price} — {unit_site} (score={best_score})")

            except Exception as e:
                print(f"Ошибка при обработке '{name_only}': {e}")
                results.append({
                    "store": "Перекресток",
                    "product": name_only,
                    "unit": unit_default,
                    "price": None,
                    "date": today
                })

            time.sleep(1)

    finally:
        driver.quit()

    # SAVE
    df = pd.DataFrame(results)
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
    os.makedirs(BASE_DIR, exist_ok=True)
    file_path = os.path.join(BASE_DIR, "perekrestok_prices.csv")
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    print(f"Сохранено {len(df)} записей в {file_path}")

# ----------------------
if __name__ == "__main__":
    main()
