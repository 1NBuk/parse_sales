import time
import pandas as pd
import re
import urllib.parse
from datetime import datetime
import os
import sys

# Добавляем путь к utils в sys.path
sys.path.append(os.path.dirname(__file__))

try:
    from driver_utils import create_driver
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz

products = [
    "Яйцо куриное Окское отборное С1 10шт",
    "Батон Коломенский Нарезной 200г",
    "Молоко Простоквашино отборное пастеризованное 3.4-4.5%",
    "Сахар кусковой белый 1кг",
    "Соль пищевая 1кг",
    "Крупа гречневая Мистраль 900г",
    "Масло Олейна подсолнечное 1л",
    "Масло Брест-Литовск сливочное 82,5% 180г",
    "Филе грудки цыпленка Петелинка",
    "Чай Greenfield Kenyan Sunrise чёрный байховый 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь отечественная",
    "Капуста белокочанная",
    "Яблоки сезонные"
]


def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        unit = match.group(1)
        name = product.replace(unit, "").strip()
    else:
        unit = ""
        name = product
    return name, unit


def main():
    results = []
    today = datetime.today().strftime("%Y-%m-%d")

    driver = create_driver(use_uc=True)

    try:
        for product in products:
            name_only, unit_default = split_name_unit(product)
            encoded_query = urllib.parse.quote(name_only)
            url = f"https://www.perekrestok.ru/cat/search?search={encoded_query}"
            driver.get(url)

            try:
                cards = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".product-card"))
                )

                selected_card = None
                max_score = 0
                price = None
                unit_from_site = unit_default or "1000 гр"

                # Проходим по всем карточкам и выбираем по максимальному score
                for card in cards:
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, ".product-card__title")
                        title_text = title_elem.text.strip().lower()
                        score = fuzz.token_sort_ratio(name_only.lower(), title_text)

                        if score > max_score:
                            max_score = score
                            selected_card = card
                    except:
                        continue

                if selected_card and max_score > 50:  # фильтр по минимальному сходству
                    # Получаем цену
                    for selector in [".price-new", ".product-card-price__current", ".product-card-price__discount"]:
                        try:
                            elem = selected_card.find_element(By.CSS_SELECTOR, selector)
                            text = elem.text.strip()
                            if text:
                                price = text.replace("Цена", "").strip()
                                break
                        except:
                            continue

                    # Получаем unit
                    try:
                        unit_elem = selected_card.find_element(By.CSS_SELECTOR, ".product-card__size")
                        if unit_elem.text.strip():
                            unit_from_site = unit_elem.text.strip()
                    except:
                        pass

                    if not unit_from_site:
                        unit_from_site = "1000 гр"

                    print(f"Перекресток — {name_only} — {price} — {unit_from_site} (score: {max_score})")

                else:
                    print(f"Перекресток — {name_only} — товар не найден")
                    price = None

                results.append({
                    "store": "Перекресток",
                    "product": name_only,
                    "unit": unit_from_site,
                    "price": price,
                    "date": today
                })

            except:
                print(f"Перекресток — {name_only} — ошибка при поиске")
                results.append({
                    "store": "Перекресток",
                    "product": name_only,
                    "unit": unit_default or "1000 гр",
                    "price": None,
                    "date": today
                })

            time.sleep(1)

    finally:
        driver.quit()

    # ===== Сохраняем CSV =====
    df = pd.DataFrame(results)
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
    os.makedirs(BASE_DIR, exist_ok=True)
    file_path = os.path.join(BASE_DIR, "perekrestok_prices.csv")
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    print(f"Сохранено {len(df)} записей в {file_path}")


if __name__ == "__main__":
    main()