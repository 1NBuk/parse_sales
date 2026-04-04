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
from rapidfuzz import fuzz

try:
    input_data = sys.stdin.read()
    if input_data:
        PRODUCTS = json.loads(input_data)
    else:
        PRODUCTS = []
    print(f"Получено продуктов: {len(PRODUCTS)}", file=sys.stderr)
except Exception as e:
    PRODUCTS = []
    print(f"Ошибка чтения: {e}", file=sys.stderr)

if not PRODUCTS:
    PRODUCTS = [
        "Яйцо куриное Окское С1 10шт",
        "Батон Коломенский Нарезной 200г",
        "Молоко Простоквашино отборное",
        "Сахар кусковой белый 1кг",
        "Соль пищевая 1кг",
        "Крупа гречневая Мистраль 900г",
        "Масло Олейна подсолнечное 1л",
        "Масло Брест-Литовск сливочное 82,5% 180г",
        "Филе цыплят-бройлеров охлаждённое Петелинка",
        "Чай Greenfield Golden Ceylon 100г",
        "Картофель белый 1кг",
        "Лук репчатый",
        "морковь вес",
        "Капуста белокочанная",
        "Яблоки сезонные"
    ]

BASE_DIR_DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
OUTPUT_FILE = os.path.join(BASE_DIR_DATA, "globus_prices.csv")
os.makedirs(BASE_DIR_DATA, exist_ok=True)


def split_name_unit(product: str):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""


def normalize_product_name(name: str) -> str:
    return "Яблоки" if name.lower().strip() == "яблоки сезонные" else name


def parse_price(price_main, price_sub_list):
    price_sub = price_sub_list[0].text.strip() if price_sub_list else "00"
    price_str = f"{price_main}.{price_sub}".replace(",", ".")
    try:
        return float(price_str)
    except:
        return None


def extract_unit(info_text, default_unit):
    match = re.search(r"(\d+\s?(г|кг|мл|л|шт))", info_text, re.IGNORECASE)
    return match.group(1) if match else default_unit


def main():
    if not PRODUCTS:
        sys.stdout.write(json.dumps([], ensure_ascii=False))
        return

    results = []
    today = datetime.today().strftime("%Y-%m-%d")
    driver = None

    try:
        driver = create_driver(use_uc=True)
        driver.get("https://globus.ru/")
        time.sleep(4)

        try:
            btn = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "span.js-select-town.button-select.see"))
            )
            driver.execute_script("arguments[0].click();", btn)
            print("Кнопка выбрана", file=sys.stderr)
            time.sleep(1)
        except:
            print("Кнопка не появилась", file=sys.stderr)

        for product in PRODUCTS:
            product_clean = product.strip().strip('"').strip("'").strip()
            product_clean = re.sub(r'^["\']+|["\']+$', '', product_clean)
            if product_clean.endswith(','):
                product_clean = product_clean[:-1]

            print(f"Ищем: {product_clean}", file=sys.stderr)
            name_only, unit_default = split_name_unit(product_clean)
            unit_default = unit_default or "1 кг"

            try:
                search_box = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input.search-form__input.js-search-form__input"))
                )
                search_box.clear()
                search_box.send_keys(product_clean)
                search_box.send_keys(Keys.ENTER)
                time.sleep(2)

                links = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul li a"))
                )

                candidates = []
                for link in links:
                    title = link.text.strip()
                    href = link.get_attribute("href")
                    if title and href:
                        score = fuzz.token_sort_ratio(name_only.lower(), title.lower())
                        candidates.append((title, href, score))

                if not candidates:
                    print(f"{product_clean} — результатов не найдено", file=sys.stderr)
                    results.append({
                        "store": "Глобус",
                        "product": normalize_product_name(product_clean),
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                best_title, best_url, best_score = max(candidates, key=lambda x: x[2])

                if best_score < 25:
                    print(f"{product_clean} — плохое совпадение (score={best_score})", file=sys.stderr)
                    results.append({
                        "store": "Глобус",
                        "product": normalize_product_name(product_clean),
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                print(f"Лучшее совпадение: {best_title} (score={best_score})", file=sys.stderr)

                driver.get(best_url)
                time.sleep(2)

                try:
                    price_main = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".catalog-detail__item-price-actual-main"))
                    ).text.strip()
                    price_sub_list = driver.find_elements(By.CSS_SELECTOR, ".catalog-detail__item-price-actual-sub")
                    price = parse_price(price_main, price_sub_list)
                except:
                    price = None

                try:
                    info_text = driver.find_element(By.CSS_SELECTOR, ".product-info").text
                    unit = extract_unit(info_text, unit_default)
                except:
                    unit = unit_default

                results.append({
                    "store": "Глобус",
                    "product": normalize_product_name(product_clean),
                    "unit": unit,
                    "price": price,
                    "date": today
                })

                print(f"{normalize_product_name(product_clean)} — {price} — {unit}", file=sys.stderr)

            except Exception as e:
                print(f"Ошибка: {e}", file=sys.stderr)
                results.append({
                    "store": "Глобус",
                    "product": normalize_product_name(product_clean),
                    "unit": unit_default,
                    "price": None,
                    "date": today
                })

            time.sleep(1)

    except Exception as e:
        print(f"Критическая ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    try:
        df = pd.DataFrame(results)
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"Сохранено {len(results)} записей в {OUTPUT_FILE}", file=sys.stderr)
        found_count = df[df['price'].notna()].shape[0]
        print(f"Найдено цен: {found_count} из {len(df)}", file=sys.stderr)
    except Exception as e:
        print(f"Ошибка сохранения: {e}", file=sys.stderr)

    json_output = json.dumps(results, ensure_ascii=False)
    sys.stdout.write(json_output)
    sys.stdout.flush()


if __name__ == "__main__":
    main()