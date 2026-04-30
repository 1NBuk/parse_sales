import time
import pandas as pd
from datetime import datetime
import re
import os
import sys
import json
import random
import logging
import warnings

# ===================== НАСТРОЙКА =====================
warnings.filterwarnings("ignore")
logging.getLogger("selenium").setLevel(logging.CRITICAL)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, BASE_DIR)

# ===================== DRIVER =====================
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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===================== INPUT =====================
def read_products():
    try:
        data = sys.stdin.read()
        if data:
            return json.loads(data)
    except:
        pass
    return []

products = read_products()

if not products:
    products = [
        "Яйцо куриное С1 10шт",
        "Молоко 1л",
        "Хлеб белый 500г"
    ]

# ===================== UTILS =====================
def log(msg):
    print(msg, file=sys.stderr)

def human_delay(a=0.5, b=1.2):
    time.sleep(random.uniform(a, b))

def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""

def clear_search(driver):
    try:
        box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='search'], input#search"))
        )
        box.click()
        box.send_keys(Keys.CONTROL + "a")
        box.send_keys(Keys.DELETE)
        driver.execute_script("arguments[0].value=''", box)
        return box
    except:
        return None

def extract_price(card):
    try:
        text = card.text
        m = re.search(r"(\d+[.,]?\d*)\s?₽", text)
        if m:
            return float(m.group(1).replace(",", "."))
    except:
        pass
    return None

# ===================== MAIN =====================
def main():
    results = []
    today = datetime.today().strftime("%Y-%m-%d")

    driver = None

    try:
        driver = create_driver(use_uc=True)

        log("Открываем сайт...")
        driver.get("https://www.auchan.ru")
        time.sleep(5)

        # cookies
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Согласен')]"))
            )
            btn.click()
        except:
            pass

        for product in products:
            try:
                product = product.strip()
                name_only, unit_default = split_name_unit(product)
                if not unit_default:
                    unit_default = "1 кг"

                log(f"Ищем: {product}")

                box = clear_search(driver)
                if not box:
                    raise Exception("Нет поля поиска")

                for ch in product:
                    box.send_keys(ch)
                    time.sleep(0.05)

                box.send_keys(Keys.ENTER)
                time.sleep(3)

                cards = WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "[data-testid='productCard-container']")
                    )
                )

                best = None
                best_score = -1

                for card in cards[:5]:
                    try:
                        title = card.text.split("\n")[0]
                        score = len(set(name_only.lower().split()) & set(title.lower().split()))
                        if score > best_score:
                            best_score = score
                            best = card
                    except:
                        continue

                if not best:
                    raise Exception("Не найдено")

                price = extract_price(best)

                unit = unit_default
                m = re.search(r"(\d+\s?(г|кг|мл|л|шт))", best.text.lower())
                if m:
                    unit = m.group(1)

                results.append({
                    "store": "Ашан",
                    "product": product,
                    "unit": unit,
                    "price": price,
                    "date": today
                })

                log(f"OK: {product} -> {price}")

            except Exception as e:
                log(f"Ошибка: {product} -> {e}")
                results.append({
                    "store": "Ашан",
                    "product": product,
                    "unit": "1 шт",
                    "price": None,
                    "date": today
                })

            time.sleep(random.uniform(2, 4))

    except Exception as e:
        log(f"Критическая ошибка: {e}")

    finally:
        if driver:
            driver.quit()

    # ===================== SAVE =====================
    try:
        df = pd.DataFrame(results)
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
        os.makedirs(data_dir, exist_ok=True)
        df.to_csv(os.path.join(data_dir, "auchan_prices.csv"), index=False)
    except:
        pass

    # ===================== OUTPUT =====================
    sys.stdout.write(json.dumps(results, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()