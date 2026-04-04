import time
import pandas as pd
from datetime import datetime
import re
import os
import sys
import json
import warnings
import logging

warnings.filterwarnings('ignore')
os.environ['WDM_LOG'] = '0'
os.environ['WDM_PRINT'] = '0'

logging.getLogger('selenium').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('webdriver_manager').setLevel(logging.ERROR)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)

original_stdout = sys.stdout
sys.stdout = sys.stderr

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

sys.stdout = original_stdout

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from rapidfuzz import fuzz

try:
    input_data = sys.stdin.read()
    if input_data:
        products = json.loads(input_data)
    else:
        products = []
except Exception as e:
    products = []

if not products:
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


def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""


def extract_price(card, driver):
    selectors = [
        ".digi-product-price-variant_actual",
        ".digi-product__price .digi-product-price-variant_actual",
        ".product-price__current",
        "[data-testid='product-price']"
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
    if not products:
        sys.stdout.write(json.dumps([], ensure_ascii=False))
        return

    driver = None

    try:
        driver = create_driver(use_uc=True)

        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        print("Загрузка главной страницы Ашан...", file=sys.stderr)
        driver.get("https://www.auchan.ru")
        time.sleep(5)

        try:
            cookie_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='cookie-accept']"))
            )
            cookie_btn.click()
            time.sleep(1)
            print("Куки приняты", file=sys.stderr)
        except:
            print("Куки не найдены", file=sys.stderr)

        for product in products:
            product_clean = product.strip().strip('"').strip("'").strip()
            product_clean = re.sub(r'^["\']+|["\']+$', '', product_clean)
            if product_clean.endswith(','):
                product_clean = product_clean[:-1]

            name_only, unit_default = split_name_unit(product_clean)

            if not unit_default:
                unit_default = "1 кг"

            print(f"Ищем: {product_clean}", file=sys.stderr)

            try:
                search_box = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input#search, input[type='search']"))
                )
                search_box.clear()
                time.sleep(0.5)
                search_box.send_keys(product_clean)
                time.sleep(1)
                search_box.send_keys(Keys.ENTER)

                time.sleep(3)

                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, "div.digi-product, div.product-card, .catalog-card")
                        )
                    )
                except TimeoutException:
                    print(f"Ашан — {product_clean} — нет результатов поиска", file=sys.stderr)
                    results.append({
                        "store": "Ашан",
                        "product": product_clean,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                time.sleep(2)

                cards = driver.find_elements(By.CSS_SELECTOR, "div.digi-product, div.product-card, .catalog-card")
                print(f"Найдено карточек: {len(cards)}", file=sys.stderr)

                best_index = None
                best_score = -1

                for idx, card in enumerate(cards):
                    title = ""
                    for sel in ["a.digi-product__label", ".digi-product__label", "a.product-card__title",
                                ".product-card__title", "h3 a", ".card-title"]:
                        try:
                            elem = card.find_element(By.CSS_SELECTOR, sel)
                            title = elem.text.strip()
                            if title:
                                break
                        except:
                            continue

                    if not title:
                        try:
                            title = card.text.split("\n")[0]
                        except:
                            continue

                    if title:
                        score = fuzz.token_sort_ratio(name_only.lower(), title.lower())
                        print(f"  Карточка {idx}: {title[:50]}... score={score}", file=sys.stderr)
                        if score > best_score:
                            best_score = score
                            best_index = idx

                if best_index is None or best_score < 30:
                    print(f"Ашан — {product_clean} — товар не найден (score={best_score})", file=sys.stderr)
                    results.append({
                        "store": "Ашан",
                        "product": product_clean,
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                cards = driver.find_elements(By.CSS_SELECTOR, "div.digi-product, div.product-card, .catalog-card")
                best_card = cards[best_index]

                price = extract_price(best_card, driver)

                card_text = best_card.text
                match_unit = re.search(r"(\d+\s?(г|кг|мл|л|шт))", card_text, re.IGNORECASE)
                unit_site = match_unit.group(1) if match_unit else unit_default

                results.append({
                    "store": "Ашан",
                    "product": product_clean,
                    "unit": unit_site,
                    "price": price,
                    "date": today
                })

                print(f"Ашан — {product_clean} — {price} — {unit_site} (score={best_score})", file=sys.stderr)

            except Exception as e:
                print(f"Ошибка при обработке '{product_clean}': {e}", file=sys.stderr)
                results.append({
                    "store": "Ашан",
                    "product": product_clean,
                    "unit": unit_default,
                    "price": None,
                    "date": today
                })

            time.sleep(3)

    except Exception as e:
        print(f"Критическая ошибка: {e}", file=sys.stderr)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    try:
        df = pd.DataFrame(results)
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, "auchan_prices.csv")
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        print(f"Сохранено {len(df)} записей в {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"Ошибка сохранения: {e}", file=sys.stderr)

    json_output = json.dumps(results, ensure_ascii=False)
    sys.stdout.write(json_output)
    sys.stdout.flush()


if __name__ == "__main__":
    main()