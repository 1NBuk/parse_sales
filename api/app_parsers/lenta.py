import time
import re
import os
import sys
import json
import warnings
import logging
from datetime import datetime

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

import pandas as pd
from rapidfuzz import fuzz
from urllib.parse import quote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
        "Молоко Простоквашино отборное пастеризованное",
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

BASE_DIR_DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
OUTPUT_FILE = os.path.join(BASE_DIR_DATA, "lenta_prices.csv")
os.makedirs(BASE_DIR_DATA, exist_ok=True)


def clean_price(text):
    m = re.search(r"(\d+[.,]?\d*)", text or "")
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def main():
    if not PRODUCTS:
        sys.stdout.write(json.dumps([], ensure_ascii=False))
        return

    results = []
    today = datetime.today().strftime("%Y-%m-%d")
    driver = None

    try:
        driver = create_driver(use_uc=True)
        wait = WebDriverWait(driver, 20)

        for product in PRODUCTS:
            product_clean = product.strip().strip('"').strip("'").strip()
            product_clean = re.sub(r'^["\']+|["\']+$', '', product_clean)
            if product_clean.endswith(','):
                product_clean = product_clean[:-1]

            print(f"Ищем: {product_clean}", file=sys.stderr)
            url = f"https://lenta.com/search/{quote(product_clean)}/"

            try:
                driver.get(url)
            except:
                print("Перезагрузка страницы...", file=sys.stderr)
                driver.execute_script("window.stop();")
                driver.get(url)

            time.sleep(3)

            try:
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "lu-product-card")
                    )
                )

                cards = driver.find_elements(By.CSS_SELECTOR, "lu-product-card")
                print(f"Найдено карточек: {len(cards)}", file=sys.stderr)

                best = None
                best_score = -1

                for idx, card in enumerate(cards[:20]):
                    try:
                        name = card.text
                        score = fuzz.token_sort_ratio(product_clean.lower(), name.lower())
                        print(f"  Карточка {idx}: score={score}", file=sys.stderr)
                        if score > best_score:
                            best_score = score
                            best = card
                    except:
                        continue

                if not best or best_score < 40:
                    print(f"Не найдено: {product_clean} (score={best_score})", file=sys.stderr)
                    results.append({
                        "store": "Лента",
                        "product": product_clean,
                        "unit": "1 кг",
                        "price": None,
                        "date": today
                    })
                    continue

                try:
                    price_el = best.find_element(By.CSS_SELECTOR, ".main-price")
                    price = clean_price(price_el.text)
                except:
                    price = None

                unit_match = re.search(r"(\d+\s?(г|кг|мл|л|шт))", best.text, re.IGNORECASE)
                unit = unit_match.group(1) if unit_match else "1 кг"

                print(f"Лента — {product_clean} — {price} — {unit} (score={best_score})", file=sys.stderr)

                results.append({
                    "store": "Лента",
                    "product": product_clean,
                    "unit": unit,
                    "price": price,
                    "date": today
                })

            except Exception as e:
                print(f"Ошибка: {product_clean}: {e}", file=sys.stderr)
                results.append({
                    "store": "Лента",
                    "product": product_clean,
                    "unit": "1 кг",
                    "price": None,
                    "date": today
                })

            time.sleep(2)

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