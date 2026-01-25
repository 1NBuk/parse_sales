import time
import pandas as pd
from datetime import datetime
import re
import urllib.parse
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

# Список продуктов
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
    "Чай Greenfield Golden Ceylon 100г",
    "Картофель",
    "Лук репчатый",
    "Морковь",
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

    driver = create_driver(use_uc=False)  # Для Дикси обычный драйвер

    try:
        for product in products:
            name_only, unit_default = split_name_unit(product)
            encoded_query = urllib.parse.quote(product)
            url = f"https://dixy.ru/catalog/?q={encoded_query}"
            driver.get(url)

            time.sleep(2)  # подождать загрузку страницы

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article.card.bs-state"))
                )

                cards = driver.find_elements(By.CSS_SELECTOR, "article.card.bs-state")
                selected_card = None
                max_score = 0

                # ищем максимально похожий товар
                for card in cards:
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, "p.card__title")
                        title_text = title_elem.text.strip().lower()
                        score = fuzz.token_sort_ratio(name_only.lower(), title_text)
                        if score > max_score:
                            max_score = score
                            selected_card = card
                    except:
                        continue

                if selected_card and max_score > 20:
                    # получить цену
                    try:
                        price_block = selected_card.find_element(By.CSS_SELECTOR, "div.card__price-num")
                        main_part = re.search(r'\d+', price_block.text).group()
                        spans = price_block.find_elements(By.TAG_NAME, "span")
                        frac_part = spans[0].text.strip() if spans else "00"
                        price = f"{main_part},{frac_part} ₽"
                    except:
                        price = None

                    # получить единицу
                    try:
                        text = selected_card.text
                        match_unit = re.search(r"(\d+\s?(г|кг|мл|л|шт))", text)
                        unit_from_site = match_unit.group(1) if match_unit else unit_default or "1000 гр"
                    except:
                        unit_from_site = unit_default or "1000 гр"

                    results.append({
                        "store": "Дикси",
                        "product": product,
                        "unit": unit_from_site,
                        "price": price,
                        "date": today
                    })
                    print(f"{name_only} — {price} — {unit_from_site} (score: {max_score})")

                else:
                    print(f"Дикси — {name_only} — товар не найден (max score {max_score})")
                    results.append({
                        "store": "Дикси",
                        "product": product,
                        "unit": unit_default or "1000 гр",
                        "price": None,
                        "date": today
                    })

            except Exception as e:
                print(f"Дикси — {name_only} — ошибка: {e}")
                results.append({
                    "store": "Дикси",
                    "product": product,
                    "unit": unit_default or "1000 гр",
                    "price": None,
                    "date": today
                })

            time.sleep(2)

    finally:
        driver.quit()

    # сохраняем CSV
    df = pd.DataFrame(results)
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
    os.makedirs(BASE_DIR, exist_ok=True)
    file_path = os.path.join(BASE_DIR, "dixy_prices.csv")
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    print(f"Сохранено {len(df)} записей в {file_path}")


if __name__ == "__main__":
    main()