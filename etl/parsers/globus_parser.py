import time
import pandas as pd
from datetime import datetime
import re
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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rapidfuzz import fuzz

products = [
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

results = []
today = datetime.today().strftime("%Y-%m-%d")


# -------------------------------------------------------------
def split_name_unit(product):
    match = re.search(r"(\d+(\.\d+)?\s?(г|кг|мл|л|шт))", product, re.IGNORECASE)
    if match:
        return product.replace(match.group(1), "").strip(), match.group(1)
    return product, ""


def normalize_product_name(name: str) -> str:
    """Для сохранения в CSV"""
    if name.lower().strip() == "яблоки сезонные":
        return "Яблоки"
    return name


def main():
    driver = create_driver(use_uc=True)  # Для Глобуса используем UC

    try:
        driver.get("https://globus.ru/")
        time.sleep(4)

        # -------------------------------------------------------------
        # Кнопка "Выбрать город"
        # -------------------------------------------------------------
        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "span.js-select-town.button-select.see"))
            )
            driver.execute_script("arguments[0].click();", btn)
            print("Кнопка «Выбрать» нажата")
            time.sleep(1)
        except:
            print("Кнопка «Выбрать» не появилась")

        # -------------------------------------------------------------
        # Основной цикл
        # -------------------------------------------------------------
        for product in products:
            print(f"\nИщем: {product}")
            name_only, unit_default = split_name_unit(product)
            if not unit_default:
                unit_default = "1 кг"

            try:
                # Поиск
                search_box = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input.search-form__input.js-search-form__input"))
                )
                search_box.clear()
                search_box.send_keys(product)
                search_box.send_keys(Keys.ENTER)
                time.sleep(2)

                # Список результатов
                links = WebDriverWait(driver, 10).until(
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
                    print(f"{product} — результатов не найдено")
                    results.append({
                        "store": "Глобус",
                        "product": normalize_product_name(product),
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                best_title, best_url, best_score = max(candidates, key=lambda x: x[2])

                if best_score < 25:
                    print(f"{product} — плохое совпадение (score={best_score})")
                    results.append({
                        "store": "Глобус",
                        "product": normalize_product_name(product),
                        "unit": unit_default,
                        "price": None,
                        "date": today
                    })
                    continue

                print(f"Лучшее совпадение: {best_title} (score={best_score})")

                # Переход на товар
                driver.get(best_url)
                time.sleep(2)

                # Цена
                try:
                    price_main = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".catalog-detail__item-price-actual-main"))
                    ).text.strip()

                    price_sub_el = driver.find_elements(By.CSS_SELECTOR, ".catalog-detail__item-price-actual-sub")
                    price_sub = price_sub_el[0].text.strip() if price_sub_el else "00"

                    price = f"{price_main}.{price_sub} ₽"
                except:
                    price = None

                # Вес
                try:
                    info_text = driver.find_element(By.CSS_SELECTOR, ".product-info").text
                    unit_match = re.search(r"(\d+\s?(г|кг|мл|л|шт))", info_text)
                    unit = unit_match.group(1) if unit_match else unit_default
                except:
                    unit = unit_default

                # Сохранение
                save_name = normalize_product_name(product)

                results.append({
                    "store": "Глобус",
                    "product": save_name,
                    "unit": unit,
                    "price": price,
                    "date": today
                })

                print(f"{save_name} — {price} — {unit}")

            except Exception as e:
                print(f"Ошибка: {e}")
                results.append({
                    "store": "Глобус",
                    "product": normalize_product_name(product),
                    "unit": unit_default,
                    "price": None,
                    "date": today
                })

            time.sleep(1)

    finally:
        driver.quit()

    # -------------------------------------------------------------
    # Завершение
    # -------------------------------------------------------------
    df = pd.DataFrame(results)
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
    os.makedirs(BASE_DIR, exist_ok=True)
    file_path = os.path.join(BASE_DIR, "globus_prices.csv")
    df.to_csv(file_path, index=False, encoding="utf-8-sig")

    print(f"Сохранено {len(df)} записей в {file_path}")


if __name__ == "__main__":
    main()