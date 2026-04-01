import time
import pandas as pd
from datetime import datetime
import re
import os
import sys
import json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)

try:
    from etl.driver_utils import create_driver
except ImportError:
    # Альтернативный импорт для запуска из консоли
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "driver_utils",
        os.path.join(os.path.dirname(__file__), "driver_utils.py")
    )
    driver_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver_utils)
    create_driver = driver_utils.create_driver

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz

if len(sys.argv) > 1:
    try:
        products = json.loads(sys.argv[1])  # ожидаем JSON-строку
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
        "Социальный товар Морковь",
        "Капуста белокочанная",
        "Яблоки сезонные"
    ]

results = []
today = datetime.today().strftime("%Y-%m-%d")


# -------------------------------------------------------------
def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""  # если нет веса, unit_default будет пустым


# -------------------------------------------------------------
def extract_price(card, driver):
    """Надёжный поиск цены через CSS и JS fallback."""
    selectors = [
        ".digi-product-price-variant_actual",
        ".digi-product__price .digi-product-price-variant_actual",
    ]
    for sel in selectors:
        try:
            elem = card.find_element(By.CSS_SELECTOR, sel)
            raw = elem.text.strip()
            m = re.search(r"(\d+[.,]?\d*)", raw)
            if m:
                return float(m.group(1).replace(",", "."))
        except:
            continue

    # fallback через JS
    try:
        js = driver.execute_script("""
            let el = arguments[0].querySelector(".digi-product-price-variant_actual");
            return el ? el.textContent : null;
        """, card)
        if js:
            m = re.search(r"(\d+[.,]?\d*)", js)
            if m:
                return float(m.group(1).replace(",", "."))
    except:
        pass

    return None


def main():
    driver = create_driver(use_uc=True)

    try:
        driver.get("https://www.auchan.ru")
        time.sleep(3)

        # -------------------------------------------------------------
        # MAIN LOOP
        # -------------------------------------------------------------
        for product in products:
            name_only, unit_default = split_name_unit(product)

            if not unit_default:
                unit_default = "1 кг"

            try:
                search_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input#search"))
                )
                search_box.clear()
                search_box.send_keys(product)
                search_box.send_keys(Keys.ENTER)

                WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "div.digi-product, div.product-card")
                    )
                )

                time.sleep(1.5)

                cards = driver.find_elements(By.CSS_SELECTOR, "div.digi-product, div.product-card")

                best_index = None
                best_score = -1

                for idx in range(len(cards)):
                    cards = driver.find_elements(By.CSS_SELECTOR, "div.digi-product, div.product-card")
                    card = cards[idx]

                    title = ""
                    for sel in ["a.digi-product__label", ".digi-product__label", "a.product-card__title"]:
                        try:
                            title = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                            break
                        except:
                            continue

                    if not title:
                        continue

                    score = fuzz.token_sort_ratio(name_only.lower(), title.lower())
                    if score > best_score:
                        best_score = score
                        best_index = idx

                if best_index is None or best_score < 25:
                    print(f"Ашан — {product} — товар не найден (score={best_score})", file=sys.stderr)
                    results.append({
                        "store": "Ашан",
                        "product": product,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                cards = driver.find_elements(By.CSS_SELECTOR, "div.digi-product, div.product-card")
                best_card = cards[best_index]

                price = extract_price(best_card, driver)

                card_text = best_card.text
                match_unit = re.search(r"(\d+\s?(г|кг|мл|л|шт))", card_text)
                unit_site = match_unit.group(1) if match_unit else unit_default

                results.append({
                    "store": "Ашан",
                    "product": product,
                    "unit": unit_site,
                    "price": price,
                    "date": today
                })

                print(f"Ашан — {product} — {price} — {unit_site} (score={best_score})", file=sys.stderr)

            except Exception as e:
                print(f"Ошибка при обработке '{product}': {e}", file=sys.stderr)
                results.append({
                    "store": "Ашан",
                    "product": product,
                    "unit": unit_default,
                    "price": None,
                    "date": today
                })

            time.sleep(2)

    finally:
        driver.quit()

    # -------------------------------------------------------------
    # SAVE
    # -------------------------------------------------------------
    df = pd.DataFrame(results)
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, "auchan_prices.csv")
    df.to_csv(file_path, index=False, encoding="utf-8-sig")

    print(f"Сохранено {len(df)} записей в {file_path}", file=sys.stderr)

    # Вывод JSON в stdout
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()